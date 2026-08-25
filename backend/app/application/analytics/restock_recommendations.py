from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.analytics.repository import RestockRecommendation
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse

SALE_PERIOD_DAYS = 30


@dataclass(frozen=True)
class RestockRecommendationsQuery:
    warehouse_id: int | None = None
    sale_period_days: int = SALE_PERIOD_DAYS


class GetRestockRecommendationsUseCase:
    """Товары, которые заканчиваются и при этом хорошо продаются — стоит дозаказать."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(
        self, actor: Actor, query: RestockRecommendationsQuery
    ) -> list[RestockRecommendation]:
        require(actor, Permission.STOCK_VIEW)
        sale_period_from = datetime.now() - timedelta(days=query.sale_period_days)

        if query.warehouse_id is not None:
            require_warehouse(actor, query.warehouse_id)
            warehouse_ids = [query.warehouse_id]
        else:
            warehouse_ids = actor.warehouse_ids

        async with self._uow as uow:
            return await uow.analytics.restock_recommendations(sale_period_from, warehouse_ids)
