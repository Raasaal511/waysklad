from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.analytics.repository import DeadStockItem, StockValueItem
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require

STALE_DAYS = 60


@dataclass(frozen=True)
class DeadStockQuery:
    stale_days: int = STALE_DAYS


class GetDeadStockUseCase:
    """Товары, не продающиеся 60+ дней (при наличии остатка)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, query: DeadStockQuery) -> list[DeadStockItem]:
        require(actor, Permission.ANALYTICS_VIEW)
        stale_after = date.today() - timedelta(days=query.stale_days)
        async with self._uow as uow:
            return await uow.analytics.dead_stock(stale_after, actor.warehouse_ids)


class GetStockValueUseCase:
    """«Деньги в товаре»: остаток × закупочная цена, по каждому товару."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[StockValueItem]:
        require(actor, Permission.ANALYTICS_VIEW)
        async with self._uow as uow:
            return await uow.analytics.stock_value(actor.warehouse_ids)
