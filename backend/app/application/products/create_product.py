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
class VariantInput:
    size: str = ""
    color: str = ""
    barcode: str | None = None


@dataclass(frozen=True)
class CreateProductCommand:
    name: str
    unit_code: str
    purchase_price: Decimal
    retail_price: Decimal
    sku: str = ""
    barcode: str | None = None
    category_id: int | None = None
    min_stock: Decimal = Decimal("0")
    variants: list[VariantInput] = field(default_factory=list)


class CreateProductUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateProductCommand) -> Product:
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
                if existing is not None:
                    raise DomainError(f"Штрихкод «{value}» уже используется товаром «{existing.name}»")

            product = Product(
                id=None,
                name=cmd.name,
                unit=unit,
                purchase_price=Money.of(cmd.purchase_price),
                retail_price=Money.of(cmd.retail_price),
                sku=cmd.sku,
                barcode=Barcode(cmd.barcode) if cmd.barcode else None,
                category_id=cmd.category_id,
                min_stock=cmd.min_stock,
                variants=[
                    ProductVariant(
                        id=None,
                        size=v.size,
                        color=v.color,
                        barcode=Barcode(v.barcode) if v.barcode else None,
                    )
                    for v in cmd.variants
                ],
            )
            await uow.products.add(product)
            await uow.audit.add(
                AuditEntry.record(actor, "product.create", product.id, name=product.name)
            )
            await uow.commit()
        return product
