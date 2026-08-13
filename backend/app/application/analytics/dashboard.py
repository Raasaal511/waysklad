from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.analytics.repository import PeriodTotals
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class DashboardResult:
    today: PeriodTotals
    week: PeriodTotals
    month: PeriodTotals


class GetDashboardUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> DashboardResult:
        require(actor, Permission.ANALYTICS_VIEW)

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        async with self._uow as uow:
            wh = actor.warehouse_ids
            today = await uow.analytics.totals_for_period(today_start, tomorrow_start, wh)
            week = await uow.analytics.totals_for_period(week_start, tomorrow_start, wh)
            month = await uow.analytics.totals_for_period(month_start, tomorrow_start, wh)
            return DashboardResult(today=today, week=week, month=month)
