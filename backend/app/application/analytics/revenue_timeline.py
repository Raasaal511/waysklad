from dataclasses import dataclass
from datetime import datetime

from app.domain.analytics.repository import TimelineBucket, TimelinePoint
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class RevenueTimelineQuery:
    date_from: datetime
    date_to: datetime
    bucket: TimelineBucket


class GetRevenueTimelineUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, query: RevenueTimelineQuery) -> list[TimelinePoint]:
        require(actor, Permission.ANALYTICS_VIEW)
        async with self._uow as uow:
            return await uow.analytics.revenue_timeline(
                query.date_from, query.date_to, query.bucket, actor.warehouse_ids
            )
