import re
from dataclasses import dataclass
from decimal import Decimal

from app.application.storefront.visible_warehouses import (
    visible_warehouse_ids as compute_visible_warehouse_ids,
)
from app.domain.catalog.entities import Product
from app.domain.common.cache import ICache
from app.domain.common.exceptions import NotFoundError
from app.domain.marketplace.repository import MarketplaceProductRow
from app.domain.reviews.repository import ProductRatingAggregate
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 300  # 5 минут — промпт B4 п.3
_MAX_LIMIT = 20

# «первые два значимых слова названия» (промпт B4 п.2) — самые частые русские
# предлоги/союзы/частицы, которые не несут смысла для похожести товара.
# Не претендует на полноту NLP — это грубый эвристический fallback на случай
# отсутствия pg_trgm, а не основной механизм поиска похожих товаров.
_STOP_WORDS = frozenset(
    {
        "и",
        "в",
        "на",
        "с",
        "для",
        "без",
        "от",
        "до",
        "по",
        "из",
        "у",
        "к",
        "о",
        "об",
        "не",
        "а",
        "но",
        "или",
        "как",
        "же",
        "то",
        "это",
        "при",
        "за",
    }
)


def _significant_name_words(name: str, count: int = 2) -> list[str]:
    """Первые count значимых слов названия товара — без предлогов/союзов и
    без слов короче 2 символов (артикул-вставки вида «М», «XL» тоже шумят
    ILIKE-фолбэк, но короткие буквы/цифры размеров чаще всего не первые
    слова названия, поэтому фильтр по длине достаточно грубый и практичный)."""
    words = re.findall(r"[\w\-]+", name, flags=re.UNICODE)
    significant = [w for w in words if len(w) >= 2 and w.lower() not in _STOP_WORDS]
    return significant[:count]


@dataclass(frozen=True)
class GetSimilarProductsCommand:
    slug: str
    product_id: int
    scope: str  # "shop" | "marketplace"
    limit: int = 10


@dataclass(frozen=True)
class SimilarShopResult:
    shop_name: str
    products: list[Product]
    in_stock_product_ids: set[int]
    sold_count_by_product_id: dict[int, Decimal]
    rating_by_product_id: dict[int, ProductRatingAggregate]


@dataclass(frozen=True)
class GetSimilarProductsResult:
    """Ровно одно из двух полей заполнено — какое, определяет cmd.scope,
    сериализуется в общий JSON для единого cache-aside декоратора."""

    shop: SimilarShopResult | None = None
    marketplace: list[MarketplaceProductRow] | None = None

    def to_json(self) -> dict:
        if self.shop is not None:
            return {
                "scope": "shop",
                "shop_name": self.shop.shop_name,
                "products": [p.to_dict() for p in self.shop.products],
                "in_stock_product_ids": sorted(self.shop.in_stock_product_ids),
                "sold_count_by_product_id": {
                    str(pid): str(qty)
                    for pid, qty in self.shop.sold_count_by_product_id.items()
                },
                "rating_by_product_id": {
                    str(pid): {
                        "average_rating": r.average_rating,
                        "reviews_count": r.reviews_count,
                    }
                    for pid, r in self.shop.rating_by_product_id.items()
                },
            }
        return {
            "scope": "marketplace",
            "products": [p.to_dict() for p in (self.marketplace or [])],
        }

    @classmethod
    def from_json(cls, d: dict) -> "GetSimilarProductsResult":
        if d["scope"] == "shop":
            return cls(
                shop=SimilarShopResult(
                    shop_name=d["shop_name"],
                    products=[Product.from_dict(p) for p in d["products"]],
                    in_stock_product_ids=set(d["in_stock_product_ids"]),
                    sold_count_by_product_id={
                        int(pid): Decimal(qty)
                        for pid, qty in d["sold_count_by_product_id"].items()
                    },
                    rating_by_product_id={
                        int(pid): ProductRatingAggregate(**r)
                        for pid, r in d["rating_by_product_id"].items()
                    },
                )
            )
        return cls(
            marketplace=[MarketplaceProductRow.from_dict(p) for p in d["products"]]
        )


class GetSimilarProductsUseCase:
    """Похожие товары карточки B4: scope=shop — товары этого же магазина,
    scope=marketplace — товары других видимых магазинов платформы.

    Кеш на _CACHE_TTL_SECONDS (5 минут — промпт B4 п.3, дольше, чем у
    остальных storefront-кешей: список похожих меняется редко и не критичен
    к свежести). Ключ включает cmd целиком (product_id + scope + limit), так
    cached_use_case сам разводит независимые записи по scope."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def execute(
        self, cmd: GetSimilarProductsCommand
    ) -> GetSimilarProductsResult | None:
        return await self._cached_execute(cmd)

    async def _execute_uncached(
        self, cmd: GetSimilarProductsCommand
    ) -> GetSimilarProductsResult | None:
        limit = min(max(cmd.limit, 1), _MAX_LIMIT)

        async with SqlAlchemyUnitOfWork(
            None, session_factory=self._session_factory
        ) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return None

        async with SqlAlchemyUnitOfWork(
            tenant.id, session_factory=self._session_factory
        ) as uow:
            try:
                product = await uow.products.get(cmd.product_id)
            except NotFoundError:
                return None
            if not product.show_on_storefront:
                return None

            categories = await uow.categories.list()
            by_id = {c.id: c for c in categories}
            category = (
                by_id.get(product.category_id)
                if product.category_id is not None
                else None
            )
            parent_category_id = category.parent_id if category is not None else None

            if cmd.scope == "shop":
                warehouse_ids = sorted(
                    compute_visible_warehouse_ids(await uow.warehouses.list())
                )
                similar = await uow.products.list_similar_in_shop(
                    product_id=product.id,
                    category_id=product.category_id,
                    parent_category_id=parent_category_id,
                    warehouse_ids=warehouse_ids,
                    limit=limit,
                )
                product_ids = [p.id for p in similar if p.id is not None]
                sold_counts = await uow.analytics.sold_count_by_products(product_ids)
                ratings = await uow.reviews.rating_by_products(product_ids)
                stock_items = await uow.stock.list_all()
                visible_warehouse_ids = set(warehouse_ids)
                in_stock_ids = {
                    pid
                    for pid in product_ids
                    if any(
                        item.product_id == pid
                        and item.quantity > 0
                        and item.warehouse_id in visible_warehouse_ids
                        for item in stock_items
                    )
                }
                return GetSimilarProductsResult(
                    shop=SimilarShopResult(
                        shop_name=tenant.name,
                        products=similar,
                        in_stock_product_ids=in_stock_ids,
                        sold_count_by_product_id=sold_counts,
                        rating_by_product_id=ratings,
                    )
                )

            # scope == "marketplace"
            category_name = category.name if category is not None else None
            name_words = _significant_name_words(product.name)

        async with SqlAlchemyUnitOfWork(
            None, session_factory=self._session_factory
        ) as public_uow:
            all_tenants = await public_uow.tenants.list_all()
            visible_tenant_ids = [
                t.id for t in all_tenants if t.storefront_enabled and not t.is_suspended
            ]
            warehouse_ids = (
                await public_uow.marketplace_products.list_visible_warehouse_ids(
                    visible_tenant_ids
                )
            )
            rows = await public_uow.marketplace_products.list_similar_cross_shop(
                visible_tenant_ids=visible_tenant_ids,
                warehouse_ids=warehouse_ids,
                exclude_product_id=product.id,
                exclude_tenant_id=tenant.id,
                category_name=category_name,
                name_words=name_words,
                limit=limit,
            )
        return GetSimilarProductsResult(marketplace=rows)

    _cached_execute = cached_use_case(
        "similar_products",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=GetSimilarProductsResult.from_json,
        shop_slug=lambda cmd: cmd.slug,
    )(_execute_uncached)
