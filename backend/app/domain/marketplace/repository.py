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
