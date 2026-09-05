from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product, ProductVariant
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class UpdateVariantInput:
    id: int | None  # None — новый вариант; отсутствующие в списке удаляются
    size: str = ""
    color: str = ""
    barcode: str | None = None


@dataclass(frozen=True)
class UpdateProductCommand:
    product_id: int
    name: str
    unit_code: str
    purchase_price: Decimal
    retail_price: Decimal
    sku: str = ""
    barcode: str | None = None
    category_id: int | None = None
    min_stock: Decimal = Decimal("0")
    photo: str = ""
    show_on_storefront: bool = False
    storefront_min_qty: Decimal | None = None
    storefront_step_qty: Decimal | None = None
    variants: list[UpdateVariantInput] = field(default_factory=list)


class UpdateProductUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

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

            product = Product(
                id=cmd.product_id,
                name=cmd.name,
                unit=unit,
                purchase_price=Money.of(cmd.purchase_price),
                retail_price=Money.of(cmd.retail_price),
                sku=cmd.sku,
                barcode=Barcode(cmd.barcode) if cmd.barcode else None,
                category_id=cmd.category_id,
                min_stock=cmd.min_stock,
                photo=cmd.photo,
                show_on_storefront=cmd.show_on_storefront,
                storefront_min_qty=cmd.storefront_min_qty,
                storefront_step_qty=cmd.storefront_step_qty,
                variants=[
                    ProductVariant(
                        id=v.id,
                        size=v.size,
                        color=v.color,
                        barcode=Barcode(v.barcode) if v.barcode else None,
                    )
                    for v in cmd.variants
                ],
            )
            await uow.products.save(product)
            await uow.audit.add(
                AuditEntry.record(actor, "product.update", product.id, name=product.name)
            )
            await uow.commit()
        return product
