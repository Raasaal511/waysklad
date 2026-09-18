from dataclasses import dataclass

from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.marketplace.repository import ShopChip
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 60  # тот же TTL, что у главной — тяжёлый кросс-tenant агрегат
_SORT_ALIASES = {"popular", "rating", "new"}


@dataclass(frozen=True)
class ListShopsCommand:
    city: str | None = None
    query: str = ""
    sort: str = "popular"
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class ListShopsResult:
    shops: list[ShopChip]
    total: int

    def to_json(self) -> dict:
        return {"shops": [s.to_dict() for s in self.shops], "total": self.total}

    @classmethod
    def from_json(cls, d: dict) -> "ListShopsResult":
        return cls(shops=[ShopChip.from_dict(s) for s in d["shops"]], total=d["total"])


class ListShopsUseCase:
    """Страница «Все магазины» (M-B2 п.3) — публичный список магазинов с хотя бы
    одним видимым товаром на витрине, с поиском по названию и сортировкой."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def execute(self, cmd: ListShopsCommand) -> ListShopsResult:
        if cmd.sort not in _SORT_ALIASES:
            raise DomainError(f"Неизвестная сортировка: «{cmd.sort}»")
        return await self._cached_execute(cmd)

    async def _execute_uncached(self, cmd: ListShopsCommand) -> ListShopsResult:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            all_tenants = await uow.tenants.list_all()
            visible_tenant_ids = [
                t.id for t in all_tenants if t.storefront_enabled and not t.is_suspended
            ]
            shops, total = await uow.marketplace_products.list_shop_chips(
                visible_tenant_ids,
                city=cmd.city,
                query=cmd.query,
                sort=cmd.sort,
                limit=cmd.limit,
                offset=cmd.offset,
            )
        return ListShopsResult(shops=shops, total=total)

    _cached_execute = cached_use_case(
        "marketplace_shops",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=ListShopsResult.from_json,
    )(_execute_uncached)
