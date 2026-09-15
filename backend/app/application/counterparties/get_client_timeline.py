from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.timeline import ClientTimelineEvent, TimelineEventType, at_midnight
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.orders.entities import Order
from app.domain.sales.entities import Sale
from app.domain.tasks.entities import Task


@dataclass(frozen=True)
class GetClientTimelineCommand:
    client_id: int


class GetClientTimelineUseCase:
    """Единая лента событий клиента (CRM) — продажи, заказы, долги (выдача,
    погашения, продления), задачи, отсортированные по дате. Заменяет поиск
    по четырём разным разделам, когда нужно понять «что там с этим клиентом»."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: GetClientTimelineCommand) -> list[ClientTimelineEvent]:
        require(actor, Permission.CLIENTS_VIEW)

        async with self._uow as uow:
            await uow.clients.get(cmd.client_id)  # 404 если не найден/чужой tenant

            sales, _ = await uow.sales.list(client_id=cmd.client_id, limit=1000)
            orders = await uow.orders.list_by_client(cmd.client_id)
            debts = await uow.debts.list_by_client(cmd.client_id)
            tasks = await uow.tasks.list_by_client(cmd.client_id)

        events: list[ClientTimelineEvent] = []
        events.extend(_sale_events(sales))
        events.extend(_order_events(orders))
        for debt in debts:
            events.extend(_debt_events(debt))
        events.extend(_task_events(tasks))

        events.sort(key=lambda e: e.sort_key, reverse=True)
        return events


def _sale_events(sales: list[Sale]) -> list[ClientTimelineEvent]:
    return [
        ClientTimelineEvent(
            type=TimelineEventType.SALE,
            occurred_at=sale.created_at,
            entity_id=sale.id,
            title=f"Продажа на {sale.total.amount}",
            amount=sale.total,
        )
        for sale in sales
    ]


def _order_events(orders: list[Order]) -> list[ClientTimelineEvent]:
    events = []
    for order in orders:
        created_at = order.created_at or at_midnight(order.due_date)
        events.append(
            ClientTimelineEvent(
                type=TimelineEventType.ORDER_CREATED,
                occurred_at=created_at,
                entity_id=order.id,
                title=f"Заказ №{order.number} на {order.total.amount}",
                amount=order.total,
                status=order.status.value,
            )
        )
    return events


def _debt_events(debt: Debt) -> list[ClientTimelineEvent]:
    events = [
        ClientTimelineEvent(
            type=TimelineEventType.DEBT_ISSUED,
            occurred_at=at_midnight(debt.issued_at),
            entity_id=debt.id,
            title=f"Долг оформлен на {debt.amount.amount}",
            amount=debt.amount,
        )
    ]
    for repayment in debt.repayments:
        events.append(
            ClientTimelineEvent(
                type=TimelineEventType.DEBT_REPAID,
                occurred_at=at_midnight(repayment.on),
                entity_id=debt.id,
                title=f"Погашение долга на {repayment.amount.amount}",
                amount=repayment.amount,
            )
        )
    for extension in debt.extensions:
        events.append(
            ClientTimelineEvent(
                type=TimelineEventType.DEBT_EXTENDED,
                occurred_at=at_midnight(extension.created_at),
                entity_id=debt.id,
                title=f"Срок долга перенесён на {extension.new_due_date}",
            )
        )
    return events


def _task_events(tasks: list[Task]) -> list[ClientTimelineEvent]:
    return [
        ClientTimelineEvent(
            type=TimelineEventType.TASK,
            occurred_at=task.created_at,
            entity_id=task.id,
            title=task.title,
            status=task.status.value,
        )
        for task in tasks
    ]
