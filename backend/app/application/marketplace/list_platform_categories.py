from dataclasses import dataclass

from app.domain.common.cache import ICache
from app.domain.platform.entities import PlatformCategory
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 300  # 5 минут (см. промпт M-B1 п.1)


@dataclass(frozen=True)
class ListPlatformCategoriesCommand:
    city: str | None = None


@dataclass(frozen=True)
class PlatformCategoryWithCount:
    category: PlatformCategory
    products_count: int


@dataclass(frozen=True)
class ListPlatformCategoriesResult:
    items: list[PlatformCategoryWithCount]

    def to_json(self) -> dict:
        return {
            "items": [
                {"category": i.category.to_dict(), "products_count": i.products_count}
                for i in self.items
            ]
        }

    @classmethod
    def from_json(cls, d: dict) -> "ListPlatformCategoriesResult":
        return cls(
            items=[
                PlatformCategoryWithCount(
                    category=PlatformCategory.from_dict(i["category"]),
                    products_count=i["products_count"],
                )
                for i in d["items"]
            ]
        )


class ListPlatformCategoriesUseCase:
    """Публичный справочник категорий платформы (для плиток на главной и для
    выпадающего списка владельца в форме категории магазина) — только активные,
    только с товарами (с учётом ?city=), products_count видимых товаров
    видимых магазинов. Кешируется на 5 минут."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def execute(
        self, cmd: ListPlatformCategoriesCommand
    ) -> ListPlatformCategoriesResult:
        return await self._cached_execute(cmd)

    async def _execute_uncached(
        self, cmd: ListPlatformCategoriesCommand
    ) -> ListPlatformCategoriesResult:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            all_categories = await uow.platform_categories.list_active()
            all_tenants = await uow.tenants.list_all()
            visible_tenant_ids = [
                t.id for t in all_tenants if t.storefront_enabled and not t.is_suspended
            ]
            counts = await uow.marketplace_products.count_by_platform_category(
                visible_tenant_ids, city=cmd.city
            )
        items = [
            PlatformCategoryWithCount(category=c, products_count=counts[c.id])
            for c in all_categories
            if counts.get(c.id)
        ]
        return ListPlatformCategoriesResult(items=items)

    _cached_execute = cached_use_case(
        "marketplace_platform_categories",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=ListPlatformCategoriesResult.from_json,
    )(_execute_uncached)
