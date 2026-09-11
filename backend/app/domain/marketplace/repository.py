from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class MarketplaceProductRow:
    """Read-only проекция товара для общего каталога платформы — не Product-сущность,
    т.к. собирается сразу по нескольким tenant и отдаёт только публично безопасные поля."""

    product_id: int
    name: str
    retail_price: Decimal
    photo: str
    category_name: str | None
    in_stock: bool
    min_order_qty: Decimal | None
    order_step_qty: Decimal | None
    shop_slug: str
    shop_name: str
    sku: str

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "retail_price": str(self.retail_price),
            "photo": self.photo,
            "category_name": self.category_name,
            "in_stock": self.in_stock,
            "min_order_qty": str(self.min_order_qty) if self.min_order_qty is not None else None,
            "order_step_qty": str(self.order_step_qty)
            if self.order_step_qty is not None
            else None,
            "shop_slug": self.shop_slug,
            "shop_name": self.shop_name,
            "sku": self.sku,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MarketplaceProductRow":
        return cls(
            product_id=d["product_id"],
            name=d["name"],
            retail_price=Decimal(d["retail_price"]),
            photo=d["photo"],
            category_name=d["category_name"],
            in_stock=d["in_stock"],
            min_order_qty=Decimal(d["min_order_qty"]) if d["min_order_qty"] is not None else None,
            order_step_qty=Decimal(d["order_step_qty"])
            if d["order_step_qty"] is not None
            else None,
            shop_slug=d["shop_slug"],
            shop_name=d["shop_name"],
            sku=d["sku"],
        )


class IMarketplaceProductRepository(Protocol):
    """Отдельный от IProductRepository протокол: тот завязан на SqlAlchemyRepository._tenant
    (один tenant на запрос), а общий каталог принципиально читает сразу много tenant."""

    async def list_visible_warehouse_ids(self, tenant_ids: list[int]) -> list[int]:
        """Склады с show_on_storefront=True среди переданных tenant — для расчёта наличия."""
        ...

    async def list_products(
        self,
        visible_tenant_ids: list[int],
        warehouse_ids: list[int],
        query: str = "",
        category: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        in_stock_only: bool = False,
        variant_size: str | None = None,
        variant_color: str | None = None,
        shop_slug: str | None = None,
        sort: str = "name",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceProductRow], int]: ...
