from dataclasses import dataclass

from app.domain.common.cache import ICache
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 300  # 5 минут — справочник городов меняется редко


@dataclass(frozen=True)
class ListCitiesCommand:
    """Пустая команда — сортировка/фильтров нет, но cached_use_case требует объект-ключ."""


@dataclass(frozen=True)
class CityCount:
    name: str
    shops_count: int


@dataclass(frozen=True)
class ListCitiesResult:
    cities: list[CityCount]

    def to_json(self) -> dict:
        return {"cities": [{"name": c.name, "shops_count": c.shops_count} for c in self.cities]}

    @classmethod
    def from_json(cls, d: dict) -> "ListCitiesResult":
        return cls(cities=[CityCount(name=c["name"], shops_count=c["shops_count"]) for c in d["cities"]])


class ListCitiesUseCase:
    """Публичный список городов, где есть хотя бы один магазин с включённой
    витриной — для поповера выбора города в шапке (см. промпт M-B1 п.2)."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def execute(self, cmd: ListCitiesCommand) -> ListCitiesResult:
        return await self._cached_execute(cmd)

    async def _execute_uncached(self, cmd: ListCitiesCommand) -> ListCitiesResult:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            all_tenants = await uow.tenants.list_all()
            visible_tenant_ids = [
                t.id for t in all_tenants if t.storefront_enabled and not t.is_suspended
            ]
            counts = await uow.marketplace_products.list_cities(visible_tenant_ids)
        cities = sorted(
            (CityCount(name=name, shops_count=count) for name, count in counts.items()),
            key=lambda c: c.name,
        )
        return ListCitiesResult(cities=cities)

    _cached_execute = cached_use_case(
        "marketplace_cities",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=ListCitiesResult.from_json,
    )(_execute_uncached)
