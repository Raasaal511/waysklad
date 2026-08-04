from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.catalog.barcode import Barcode
from app.domain.common.money import Money
from app.domain.common.quantity import Unit


@dataclass
class Category:
    id: int | None
    name: str
    parent_id: int | None = None


@dataclass
class ProductVariant:
    """Вариант товара: размер/цвет — критично для одежды."""

    id: int | None
    size: str = ""
    color: str = ""
    barcode: Barcode | None = None


@dataclass
class Product:
    id: int | None
    name: str
    unit: Unit
    purchase_price: Money  # закупочная — видна только владельцу
    retail_price: Money
    sku: str = ""
    barcode: Barcode | None = None
    category_id: int | None = None
    photo: str = ""
    min_stock: Decimal = Decimal("0")  # порог «заканчивается»
    variants: list[ProductVariant] = field(default_factory=list)

    @property
    def margin(self) -> Money:
        return self.retail_price - self.purchase_price
