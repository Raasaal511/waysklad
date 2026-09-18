from dataclasses import dataclass, field
from decimal import Decimal

from app.application.inventory.common import require_warehouse_access
from app.domain.audit.entities import AuditEntry
from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product, ProductVariant
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.inventory.entities import StockDocType, StockDocument, StockLine
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class VariantInput:
    size: str = ""
    color: str = ""
    barcode: str | None = None
    price: Decimal | None = None


@dataclass(frozen=True)
class CreateProductCommand:
    name: str
    unit_code: str
    purchase_price: Decimal
    retail_price: Decimal
    compare_at_price: Decimal | None = None
    sku: str = ""
    barcode: str | None = None
    category_id: int | None = None
    min_stock: Decimal = Decimal("0")
    description: str = ""
    show_on_storefront: bool = False
    storefront_min_qty: Decimal | None = None
    storefront_step_qty: Decimal | None = None
    variants: list[VariantInput] = field(default_factory=list)
    initial_stock_warehouse_id: int | None = None
    initial_stock_quantity: Decimal | None = None


class CreateProductUseCase:
    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: CreateProductCommand) -> Product:
        require(actor, Permission.PRODUCTS_MANAGE)
        has_initial_stock = (
            cmd.initial_stock_warehouse_id is not None
            and cmd.initial_stock_quantity is not None
            and cmd.initial_stock_quantity > 0
        )
        if has_initial_stock:
            require(actor, Permission.STOCK_RECEIVE)

        async with self._uow as uow:
            if has_initial_stock:
                await require_warehouse_access(uow, actor, cmd.initial_stock_warehouse_id)

            unit = await uow.units.get(cmd.unit_code)
            if unit is None:
                raise DomainError(f"Неизвестная единица измерения: {cmd.unit_code}")

            barcodes = [cmd.barcode, *(v.barcode for v in cmd.variants)]
            non_empty = [b for b in barcodes if b]
            if len(non_empty) != len(set(non_empty)):
                raise DomainError("Штрихкоды товара и его вариантов не должны повторяться")
            for value in non_empty:
                existing = await uow.products.get_by_barcode(Barcode(value))
                if existing is not None:
                    raise DomainError(f"Штрихкод «{value}» уже используется товаром «{existing.name}»")

            for qty in (cmd.storefront_min_qty, cmd.storefront_step_qty):
                if qty is not None and qty <= 0:
                    raise DomainError("Мин. количество и шаг заказа на витрине должны быть больше нуля")

            if cmd.compare_at_price is not None and cmd.compare_at_price <= cmd.retail_price:
                raise DomainError("Старая цена должна быть больше текущей")

            product = Product(
                id=None,
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
                description=cmd.description,
                show_on_storefront=cmd.show_on_storefront,
                storefront_min_qty=cmd.storefront_min_qty,
                storefront_step_qty=cmd.storefront_step_qty,
                variants=[
                    ProductVariant(
                        id=None,
                        size=v.size,
                        color=v.color,
                        barcode=Barcode(v.barcode) if v.barcode else None,
                        price=Money.of(v.price) if v.price is not None else None,
                    )
                    for v in cmd.variants
                ],
            )
            await uow.products.add(product)
            await uow.audit.add(
                AuditEntry.record(actor, "product.create", product.id, name=product.name)
            )

            if has_initial_stock:
                document = StockDocument(
                    id=None,
                    type=StockDocType.RECEIPT,
                    warehouse_id=cmd.initial_stock_warehouse_id,
                    author_id=actor.id,
                    lines=[
                        StockLine(
                            product_id=product.id,
                            quantity=Quantity(cmd.initial_stock_quantity, unit),
                        )
                    ],
                    note="Начальный остаток при создании товара",
                )
                document.post()
                await uow.stock_documents.add(document)
                await uow.stock.change(
                    product.id, cmd.initial_stock_warehouse_id, cmd.initial_stock_quantity, None
                )
                await uow.audit.add(
                    AuditEntry.record(
                        actor, "stock.receive", document.id,
                        warehouse_id=cmd.initial_stock_warehouse_id, positions=1,
                    )
                )

            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return product
