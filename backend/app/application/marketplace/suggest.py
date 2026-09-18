from dataclasses import dataclass
from decimal import Decimal

from app.domain.common.cache import ICache
from app.domain.marketplace.repository import ShopChip, SuggestProductRow
from app.domain.platform.entities import PlatformCategory
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 30  # M-B2 п.4
_MIN_QUERY_LENGTH = 2
_PRODUCTS_LIMIT = 5
_SHOPS_LIMIT = 3
_CATEGORIES_LIMIT = 3


@dataclass(frozen=True)
class SuggestCommand:
    query: str
    city: str | None = None


@dataclass(frozen=True)
class SuggestResult:
    products: list[SuggestProductRow]
    shops: list[ShopChip]
    categories: list[PlatformCategory]

    def to_json(self) -> dict:
        return {
            "products": [
                {
                    "product_id": p.product_id, "name": p.name, "photo": p.photo,
                    "retail_price": str(p.retail_price), "shop_slug": p.shop_slug,
                }
                for p in self.products
            ],
            "shops": [s.to_dict() for s in self.shops],
            "categories": [c.to_dict() for c in self.categories],
        }

    @classmethod
    def from_json(cls, d: dict) -> "SuggestResult":
        return cls(
            products=[
                SuggestProductRow(
                    product_id=p["product_id"], name=p["name"], photo=p["photo"],
                    retail_price=Decimal(p["retail_price"]), shop_slug=p["shop_slug"],
                )
                for p in d["products"]
            ],
            shops=[ShopChip.from_dict(s) for s in d["shops"]],
            categories=[PlatformCategory.from_dict(c) for c in d["categories"]],
        )


class SuggestUseCase:
    """Подсказки поиска (товары/магазины/категории) для строки поиска шапки
    маркетплейса (M-B2 п.4). Запрос короче _MIN_QUERY_LENGTH — пустой результат
    без обращения к БД (фронт всё равно не должен слать такие запросы, но
    защищаемся и здесь, как и у остальных публичных эндпоинтов)."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def execute(self, cmd: SuggestCommand) -> SuggestResult:
        if len(cmd.query.strip()) < _MIN_QUERY_LENGTH:
            return SuggestResult(products=[], shops=[], categories=[])
        return await self._cached_execute(cmd)

    async def _execute_uncached(self, cmd: SuggestCommand) -> SuggestResult:
        query = cmd.query.strip()
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            all_tenants = await uow.tenants.list_all()
            visible_tenant_ids = [
                t.id for t in all_tenants if t.storefront_enabled and not t.is_suspended
            ]
            products = await uow.marketplace_products.suggest_products(
                visible_tenant_ids, query, cmd.city, limit=_PRODUCTS_LIMIT
            )
            shops, _total = await uow.marketplace_products.list_shop_chips(
                visible_tenant_ids, city=cmd.city, query=query, sort="popular", limit=_SHOPS_LIMIT
            )
            all_categories = await uow.platform_categories.list_active()

        query_norm = query.lower()
        categories = [c for c in all_categories if query_norm in c.name.lower()][:_CATEGORIES_LIMIT]

        return SuggestResult(products=products, shops=shops, categories=categories)

    _cached_execute = cached_use_case(
        "marketplace_suggest",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=SuggestResult.from_json,
    )(_execute_uncached)
