from dataclasses import dataclass
from datetime import datetime

from app.domain.analytics.repository import MissedSaleItem
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class MissedSalesQuery:
    date_from: datetime
    date_to: datetime


class GetMissedSalesUseCase:
    """Товары, которые покупатели хотели купить на витрине, но не хватило
    остатка — противоположность GetRestockRecommendationsUseCase (тот ловит
    «заканчивается, пока ещё есть», этот — «уже кончилось, теряем продажи»)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, query: MissedSalesQuery) -> list[MissedSaleItem]:
        require(actor, Permission.ANALYTICS_VIEW)
        async with self._uow as uow:
            return await uow.analytics.missed_sales(query.date_from, query.date_to)
