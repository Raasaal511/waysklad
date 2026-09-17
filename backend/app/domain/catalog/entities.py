from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.catalog.barcode import Barcode
from app.domain.common.money import Money
from app.domain.common.quantity import UNITS, Unit


@dataclass
class Category:
    id: int | None
    name: str
    parent_id: int | None = None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "parent_id": self.parent_id}

    @classmethod
    def from_dict(cls, d: dict) -> "Category":
        return cls(id=d["id"], name=d["name"], parent_id=d["parent_id"])


@dataclass
class ProductVariant:
    """Вариант товара: размер/цвет — критично для одежды."""

    id: int | None
    size: str = ""
    color: str = ""
    barcode: Barcode | None = None
    photo: str = ""
    # None — цена варианта не задана отдельно, берётся retail_price товара
    price: Money | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "size": self.size,
            "color": self.color,
            "barcode": self.barcode.value if self.barcode else None,
            "photo": self.photo,
            "price": str(self.price.amount) if self.price else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProductVariant":
        return cls(
            id=d["id"],
            size=d["size"],
            color=d["color"],
            barcode=Barcode(d["barcode"]) if d["barcode"] else None,
            photo=d.get("photo", ""),
            price=Money.of(d["price"]) if d.get("price") else None,
        )


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
    description: str = ""  # для карточки товара на витрине, не складская характеристика
    # галерея для карточки товара на витрине — независима от складского photo
    # (то и другое можно загрузить и менять по отдельности)
    storefront_photos: list[str] = field(default_factory=list)
    min_stock: Decimal = Decimal("0")  # порог «заканчивается»
    show_on_storefront: bool = False  # видимость на публичной витрине — по умолчанию скрыт
    # ограничения заявки с витрины — действуют только там, не в обычной продаже/заказе;
    # None у обоих значит «без ограничения» (текущее поведение)
    storefront_min_qty: Decimal | None = None
    storefront_step_qty: Decimal | None = None
    variants: list[ProductVariant] = field(default_factory=list)

    @property
    def margin(self) -> Money:
        return self.retail_price - self.purchase_price

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "unit_code": self.unit.code,
            "purchase_price": str(self.purchase_price.amount),
            "retail_price": str(self.retail_price.amount),
            "sku": self.sku,
            "barcode": self.barcode.value if self.barcode else None,
            "category_id": self.category_id,
            "photo": self.photo,
            "description": self.description,
            "storefront_photos": list(self.storefront_photos),
            "min_stock": str(self.min_stock),
            "show_on_storefront": self.show_on_storefront,
            "storefront_min_qty": str(self.storefront_min_qty)
            if self.storefront_min_qty is not None
            else None,
            "storefront_step_qty": str(self.storefront_step_qty)
            if self.storefront_step_qty is not None
            else None,
            "variants": [v.to_dict() for v in self.variants],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Product":
        return cls(
            id=d["id"],
            name=d["name"],
            unit=UNITS[d["unit_code"]],
            purchase_price=Money(Decimal(d["purchase_price"])),
            retail_price=Money(Decimal(d["retail_price"])),
            sku=d["sku"],
            barcode=Barcode(d["barcode"]) if d["barcode"] else None,
            category_id=d["category_id"],
            photo=d["photo"],
            description=d.get("description", ""),
            storefront_photos=d.get("storefront_photos", []),
            min_stock=Decimal(d["min_stock"]),
            show_on_storefront=d["show_on_storefront"],
            storefront_min_qty=Decimal(d["storefront_min_qty"])
            if d["storefront_min_qty"] is not None
            else None,
            storefront_step_qty=Decimal(d["storefront_step_qty"])
            if d["storefront_step_qty"] is not None
            else None,
            variants=[ProductVariant.from_dict(v) for v in d["variants"]],
        )
