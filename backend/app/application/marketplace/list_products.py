from dataclasses import dataclass
from decimal import Decimal

from app.domain.common.exceptions import DomainError
from app.domain.marketplace.repository import MarketplaceProductRow
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

# та же публично безопасная сортировка, что у витрины одного магазина (см. storefront/get_catalog.py) —
# ни margin, ни точный stock наружу не отдаются
_SORT_ALIASES = {
    "name": "name",
    "price_asc": "price_asc",
    "price_desc": "price_desc",
    "created_desc": "created_desc",
}


@dataclass(frozen=True)
class ListMarketplaceProductsCommand:
    query: str = ""
    category: str | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    in_stock_only: bool = False
    variant_size: str | None = None
    variant_color: str | None = None
    shop_slug: str | None = None
    sort: str = "name"
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class ListMarketplaceProductsResult:
    products: list[MarketplaceProductRow]
    total: int


class ListMarketplaceProductsUseCase:
    """Публичный (без авторизации, без actor) общий каталог товаров всех магазинов платформы —
    отдельно от витрины одного магазина (GetStorefrontCatalogUseCase)."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: ListMarketplaceProductsCommand) -> ListMarketplaceProductsResult:
        if cmd.sort not in _SORT_ALIASES:
            raise DomainError(f"Неизвестная сортировка: «{cmd.sort}»")

        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            all_tenants = await uow.tenants.list_all()
            visible_tenants = [t for t in all_tenants if t.storefront_enabled]
            if cmd.shop_slug is not None:
                visible_tenants = [t for t in visible_tenants if t.slug == cmd.shop_slug]
            visible_tenant_ids = [t.id for t in visible_tenants]

            if not visible_tenant_ids:
                return ListMarketplaceProductsResult(products=[], total=0)

            warehouse_ids = await uow.marketplace_products.list_visible_warehouse_ids(
                visible_tenant_ids
            )
            products, total = await uow.marketplace_products.list_products(
                visible_tenant_ids=visible_tenant_ids,
                warehouse_ids=warehouse_ids,
                query=cmd.query,
                category=cmd.category,
                price_min=cmd.price_min,
                price_max=cmd.price_max,
                in_stock_only=cmd.in_stock_only,
                variant_size=cmd.variant_size,
                variant_color=cmd.variant_color,
                shop_slug=cmd.shop_slug,
                sort=cmd.sort,
                limit=cmd.limit,
                offset=cmd.offset,
            )
        return ListMarketplaceProductsResult(products=products, total=total)
