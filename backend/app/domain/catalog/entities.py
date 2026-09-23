from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.catalog.barcode import Barcode
from app.domain.common.money import Money
from app.domain.common.quantity import UNITS, Unit

_LOW_STOCK_FALLBACK_THRESHOLD = Decimal("3")  # min_stock не задан (=0) — считаем "мало" на глаз


def stock_level(quantity: Decimal, min_stock: Decimal) -> str:
    """"out" | "low" | "in" — для публичной витрины (промпт B1 п.2), где точный
    остаток обычно скрыт и покупателю показывают только уровень. "low" — остаток
    положительный и не выше min_stock (или 3, если владелец не задал min_stock)."""
    if quantity <= 0:
        return "out"
    threshold = min_stock if min_stock > 0 else _LOW_STOCK_FALLBACK_THRESHOLD
    return "low" if quantity <= threshold else "in"


@dataclass
class Category:
    id: int | None
    name: str
    parent_id: int | None = None
    # выбирается владельцем — привязка к общему справочнику категорий платформы
    # (app.domain.platform.entities.PlatformCategory), None — не сопоставлена
    platform_category_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "platform_category_id": self.platform_category_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Category":
        return cls(
            id=d["id"],
            name=d["name"],
            parent_id=d["parent_id"],
            platform_category_id=d.get("platform_category_id"),
        )


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
    # своё название варианта («Aurum») — если пусто, витрина строит display_name
    # из size/color (см. StorefrontProductVariantResponse.display_name)
    name: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "size": self.size,
            "color": self.color,
            "barcode": self.barcode.value if self.barcode else None,
            "photo": self.photo,
            "price": str(self.price.amount) if self.price else None,
            "name": self.name,
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
            name=d.get("name", ""),  # старые записи кеша — без поля, см. промпт B1 п.5
        )


@dataclass
class Product:
    id: int | None
    name: str
    unit: Unit
    purchase_price: Money  # закупочная — видна только владельцу
    retail_price: Money
    # обычная розничная скидка (не оптовая) — «старая цена», зачёркнутая на витрине;
    # None — скидки нет. Должна быть строго больше retail_price (см. UpdateProductUseCase)
    compare_at_price: Money | None = None
    sku: str = ""
    barcode: Barcode | None = None
    category_id: int | None = None
    photo: str = ""
    description: str = ""  # для карточки товара на витрине, не складская характеристика
    warranty_text: str = ""  # «Гарантии» на витрине — тот же характер поля, что description
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

    @property
    def old_price(self) -> Money | None:
        """Старая цена для витрины — None и когда скидки не задано, и когда
        retail_price позже подняли выше compare_at_price (скидка считается
        отсутствующей, но само поле в БД не трогаем, см. промпт M-B1 п.4), и
        когда скидка есть, но меньше 3% (old_price и discount_percent всегда
        показываются/скрываются вместе — см. discount_percent)."""
        return self.compare_at_price if self.discount_percent is not None else None

    @property
    def discount_percent(self) -> int | None:
        """Округление вниз, показывать только при >= 3% — иначе визуальный шум
        от копеечной разницы, которую владелец мог выставить случайно."""
        if self.compare_at_price is None or self.compare_at_price.amount <= self.retail_price.amount:
            return None
        percent = int(
            (self.compare_at_price.amount - self.retail_price.amount)
            / self.compare_at_price.amount * 100
        )
        return percent if percent >= 3 else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "unit_code": self.unit.code,
            "purchase_price": str(self.purchase_price.amount),
            "retail_price": str(self.retail_price.amount),
            "compare_at_price": str(self.compare_at_price.amount)
            if self.compare_at_price is not None
            else None,
            "sku": self.sku,
            "barcode": self.barcode.value if self.barcode else None,
            "category_id": self.category_id,
            "photo": self.photo,
            "description": self.description,
            "warranty_text": self.warranty_text,
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
            compare_at_price=Money(Decimal(d["compare_at_price"]))
            if d.get("compare_at_price") is not None
            else None,
            sku=d["sku"],
            barcode=Barcode(d["barcode"]) if d["barcode"] else None,
            category_id=d["category_id"],
            photo=d["photo"],
            description=d.get("description", ""),
            warranty_text=d.get("warranty_text", ""),  # старые записи кеша — без поля
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
