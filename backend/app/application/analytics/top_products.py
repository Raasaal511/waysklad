from dataclasses import dataclass
from datetime import datetime

from app.domain.analytics.repository import CategoryProfit, ProductSales
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class TopProductsQuery:
    date_from: datetime
    date_to: datetime
    limit: int = 10


class GetTopProductsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, query: TopProductsQuery) -> list[ProductSales]:
        require(actor, Permission.ANALYTICS_VIEW)
        async with self._uow as uow:
            return await uow.analytics.top_products(
                query.date_from, query.date_to, query.limit, actor.warehouse_ids
            )


@dataclass(frozen=True)
class CategoryProfitQuery:
    date_from: datetime
    date_to: datetime


class GetCategoryProfitUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, query: CategoryProfitQuery) -> list[CategoryProfit]:
        require(actor, Permission.ANALYTICS_VIEW)
        async with self._uow as uow:
            return await uow.analytics.profit_by_category(
                query.date_from, query.date_to, actor.warehouse_ids
            )
