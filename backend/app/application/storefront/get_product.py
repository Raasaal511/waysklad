from dataclasses import dataclass
from decimal import Decimal

from app.domain.catalog.entities import Product
from app.domain.common.cache import ICache
from app.domain.common.exceptions import NotFoundError
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 20


@dataclass(frozen=True)
class GetStorefrontProductCommand:
    slug: str
    product_id: int


@dataclass(frozen=True)
class StorefrontProductResult:
    shop_name: str
    product: Product
    in_stock: bool
    sold_count: Decimal

    def to_json(self) -> dict:
        return {
            "shop_name": self.shop_name,
            "product": self.product.to_dict(),
            "in_stock": self.in_stock,
            "sold_count": str(self.sold_count),
        }

    @classmethod
    def from_json(cls, d: dict) -> "StorefrontProductResult":
        return cls(
            shop_name=d["shop_name"],
            product=Product.from_dict(d["product"]),
            in_stock=d["in_stock"],
            sold_count=Decimal(d.get("sold_count", "0")),
        )


class GetStorefrontProductUseCase:
    """Карточка одного товара на публичной витрине — для отдельной ссылки,
    например «скинуть этот товар клиенту в WhatsApp».

    Результат кешируется на _CACHE_TTL_SECONDS — та же логика, что у
    GetStorefrontCatalogUseCase (короткий TTL вместо точной инвалидации)."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def _execute_uncached(
        self, cmd: GetStorefrontProductCommand
    ) -> StorefrontProductResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return None

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            try:
                product = await uow.products.get(cmd.product_id)
            except NotFoundError:
                return None
            if not product.show_on_storefront:
                return None
            stock_items = await uow.stock.list_all()
            sold_counts = await uow.analytics.sold_count_by_products([product.id])

        in_stock = any(
            item.product_id == product.id and item.quantity > 0 for item in stock_items
        )
        sold_count = sold_counts.get(product.id, Decimal("0"))
        return StorefrontProductResult(
            shop_name=tenant.name, product=product, in_stock=in_stock, sold_count=sold_count
        )

    execute = cached_use_case(
        "storefront_product",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=StorefrontProductResult.from_json,
        shop_slug=lambda cmd: cmd.slug,
    )(_execute_uncached)
