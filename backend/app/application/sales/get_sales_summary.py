from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.sales.payment import PaymentMethod


@dataclass(frozen=True)
class GetSalesSummaryCommand:
    warehouse_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None


class GetSalesSummaryUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(
        self, actor: Actor, cmd: GetSalesSummaryCommand
    ) -> dict[PaymentMethod, tuple[int, Decimal]]:
        async with self._uow as uow:
            return await uow.sales.summary_by_payment_method(
                warehouse_id=cmd.warehouse_id,
                warehouse_ids=list(actor.warehouse_ids) if actor.is_warehouse_scoped else None,
                date_from=cmd.date_from,
                date_to=cmd.date_to,
            )
