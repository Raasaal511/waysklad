from dataclasses import dataclass
from decimal import Decimal

from app.domain.catalog.entities import Product
from app.domain.common.cache import ICache
from app.domain.common.exceptions import NotFoundError
from app.domain.reviews.repository import ProductRatingAggregate
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 20
_EMPTY_RATING = ProductRatingAggregate(average_rating=0.0, reviews_count=0)


@dataclass(frozen=True)
class GetMarketplaceProductCommand:
    product_id: int


@dataclass(frozen=True)
class MarketplaceProductResult:
    shop_slug: str
    shop_name: str
    product: Product
    in_stock: bool
    sold_count: Decimal
    rating: ProductRatingAggregate

    def to_json(self) -> dict:
        return {
            "shop_slug": self.shop_slug,
            "shop_name": self.shop_name,
            "product": self.product.to_dict(),
            "in_stock": self.in_stock,
            "sold_count": str(self.sold_count),
            "rating": {
                "average_rating": self.rating.average_rating,
                "reviews_count": self.rating.reviews_count,
            },
        }

    @classmethod
    def from_json(cls, d: dict) -> "MarketplaceProductResult":
        rating_d = d.get("rating")
        return cls(
            shop_slug=d["shop_slug"],
            shop_name=d["shop_name"],
            product=Product.from_dict(d["product"]),
            in_stock=d["in_stock"],
            sold_count=Decimal(d.get("sold_count", "0")),
            rating=ProductRatingAggregate(**rating_d) if rating_d else _EMPTY_RATING,
        )


class GetMarketplaceProductUseCase:
    """Карточка одного товара из общего каталога платформы — по глобально
    уникальному product_id, без shop_slug в запросе (в отличие от
    GetStorefrontProductUseCase, где slug уже известен из URL одной витрины).

    Результат кешируется на _CACHE_TTL_SECONDS — тот же принцип, что у
    остальных публичных каталогов (короткий TTL вместо точной инвалидации)."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def _execute_uncached(
        self, cmd: GetMarketplaceProductCommand
    ) -> MarketplaceProductResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant_id = await public_uow.marketplace_products.find_tenant_by_product(cmd.product_id)
        if tenant_id is None:
            return None

        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get(tenant_id)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return None

        async with SqlAlchemyUnitOfWork(tenant_id, session_factory=self._session_factory) as uow:
            try:
                product = await uow.products.get(cmd.product_id)
            except NotFoundError:
                return None
            if not product.show_on_storefront:
                return None
            visible_warehouse_ids = {w.id for w in await uow.warehouses.list() if w.show_on_storefront}
            stock_items = await uow.stock.list_all()
            sold_counts = await uow.analytics.sold_count_by_products([product.id])
            ratings = await uow.reviews.rating_by_products([product.id])

        in_stock = any(
            item.product_id == product.id and item.quantity > 0
            and item.warehouse_id in visible_warehouse_ids
            for item in stock_items
        )
        sold_count = sold_counts.get(product.id, Decimal("0"))
        rating = ratings.get(product.id, _EMPTY_RATING)
        return MarketplaceProductResult(
            shop_slug=tenant.slug or "",
            shop_name=tenant.name,
            product=product,
            in_stock=in_stock,
            sold_count=sold_count,
            rating=rating,
        )

    execute = cached_use_case(
        "marketplace_product",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=MarketplaceProductResult.from_json,
    )(_execute_uncached)
