from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.common.uow import IUnitOfWork
from app.domain.sales.entities import Sale
from app.domain.sales.payment import PaymentMethod
from app.domain.identity.permissions import Actor


@dataclass(frozen=True)
class ListSalesCommand:
    limit: int = 50
    offset: int = 0
    client_id: int | None = None
    product_id: int | None = None
    warehouse_id: int | None = None
    payment_method: PaymentMethod | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: str = "date_desc"


@dataclass(frozen=True)
class ListSalesResult:
    sales: list[Sale]
    total: int


class ListSalesUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ListSalesCommand) -> ListSalesResult:
        async with self._uow as uow:
            sales, total = await uow.sales.list(
                limit=cmd.limit,
                offset=cmd.offset,
                client_id=cmd.client_id,
                product_id=cmd.product_id,
                warehouse_id=cmd.warehouse_id,
                warehouse_ids=list(actor.warehouse_ids) if actor.is_warehouse_scoped else None,
                payment_method=cmd.payment_method,
                date_from=cmd.date_from,
                date_to=cmd.date_to,
                sort=cmd.sort,
            )
            return ListSalesResult(sales=sales, total=total)
