from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product, ProductVariant
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class UpdateVariantInput:
    id: int | None  # None — новый вариант; отсутствующие в списке удаляются
    size: str = ""
    color: str = ""
    barcode: str | None = None
    photo: str = ""
    # None — цена не переопределена, берётся retail_price товара
    price: Decimal | None = None
    name: str = ""


@dataclass(frozen=True)
class UpdateProductCommand:
    product_id: int
    name: str
    unit_code: str
    purchase_price: Decimal
    retail_price: Decimal
    compare_at_price: Decimal | None = None
    sku: str = ""
    barcode: str | None = None
    category_id: int | None = None
    min_stock: Decimal = Decimal("0")
    photo: str = ""
    description: str = ""
    warranty_text: str = ""
    show_on_storefront: bool = False
    storefront_min_qty: Decimal | None = None
    storefront_step_qty: Decimal | None = None
    variants: list[UpdateVariantInput] = field(default_factory=list)


class UpdateProductUseCase:
    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: UpdateProductCommand) -> Product:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            unit = await uow.units.get(cmd.unit_code)
            if unit is None:
                raise DomainError(f"Неизвестная единица измерения: {cmd.unit_code}")

            barcodes = [cmd.barcode, *(v.barcode for v in cmd.variants)]
            non_empty = [b for b in barcodes if b]
            if len(non_empty) != len(set(non_empty)):
                raise DomainError("Штрихкоды товара и его вариантов не должны повторяться")
            for value in non_empty:
                existing = await uow.products.get_by_barcode(Barcode(value))
                if existing is not None and existing.id != cmd.product_id:
                    raise DomainError(f"Штрихкод «{value}» уже используется товаром «{existing.name}»")

            for qty in (cmd.storefront_min_qty, cmd.storefront_step_qty):
                if qty is not None and qty <= 0:
                    raise DomainError("Мин. количество и шаг заказа на витрине должны быть больше нуля")

            existing_product = await uow.products.get(cmd.product_id)
            existing_compare_at_price = (
                existing_product.compare_at_price.amount
                if existing_product.compare_at_price is not None
                else None
            )
            # валидация только при попытке ЗАДАТЬ/ИЗМЕНИТЬ старую цену — если её
            # не трогают, а просто подняли retail_price выше уже сохранённой
            # compare_at_price, запрос не должен падать (см. промпт M-B1 п.4:
            # «в БД не трогать», старая цена просто перестаёт быть видна на витрине)
            if (
                cmd.compare_at_price is not None
                and cmd.compare_at_price != existing_compare_at_price
                and cmd.compare_at_price <= cmd.retail_price
            ):
                raise DomainError("Старая цена должна быть больше текущей")

            product = Product(
                id=cmd.product_id,
                name=cmd.name,
                unit=unit,
                purchase_price=Money.of(cmd.purchase_price),
                retail_price=Money.of(cmd.retail_price),
                compare_at_price=Money.of(cmd.compare_at_price)
                if cmd.compare_at_price is not None
                else None,
                sku=cmd.sku,
                barcode=Barcode(cmd.barcode) if cmd.barcode else None,
                category_id=cmd.category_id,
                min_stock=cmd.min_stock,
                photo=cmd.photo,
                description=cmd.description,
                warranty_text=cmd.warranty_text,
                show_on_storefront=cmd.show_on_storefront,
                storefront_min_qty=cmd.storefront_min_qty,
                storefront_step_qty=cmd.storefront_step_qty,
                variants=[
                    ProductVariant(
                        id=v.id,
                        size=v.size,
                        color=v.color,
                        barcode=Barcode(v.barcode) if v.barcode else None,
                        photo=v.photo,
                        price=Money.of(v.price) if v.price is not None else None,
                        name=v.name,
                    )
                    for v in cmd.variants
                ],
            )
            await uow.products.save(product)
            await uow.audit.add(
                AuditEntry.record(actor, "product.update", product.id, name=product.name)
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return product
