from dataclasses import dataclass
from datetime import datetime

from app.domain.analytics.repository import PeriodTotals
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class PeriodTotalsQuery:
    date_from: datetime
    date_to: datetime


class GetPeriodTotalsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, query: PeriodTotalsQuery) -> PeriodTotals:
        require(actor, Permission.ANALYTICS_VIEW)
        async with self._uow as uow:
            return await uow.analytics.totals_for_period(
                query.date_from, query.date_to, actor.warehouse_ids
            )
