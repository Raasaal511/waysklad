from dataclasses import dataclass

from app.domain.common.money import Money
from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Client
from app.domain.debts.entities import total_balance
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.orders.entities import OrderStatus
from app.domain.tasks.entities import TaskStatus


@dataclass(frozen=True)
class GetClientSummaryCommand:
    client_id: int


@dataclass(frozen=True)
class ClientSummary:
    client: Client
    debt_balance: Money
    active_orders_count: int
    open_tasks_count: int


_ACTIVE_ORDER_STATUSES = {OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.READY}


class GetClientSummaryUseCase:
    """Карточка клиента (CRM-хаб): баланс долга и счётчики активных заказов/задач
    рядом с данными клиента — не нужно открывать три раздела, чтобы понять,
    требует ли клиент внимания."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: GetClientSummaryCommand) -> ClientSummary:
        require(actor, Permission.CLIENTS_VIEW)

        async with self._uow as uow:
            client = await uow.clients.get(cmd.client_id)
            debts = await uow.debts.list_by_client(cmd.client_id)
            orders = await uow.orders.list_by_client(cmd.client_id)
            tasks = await uow.tasks.list_by_client(cmd.client_id)

        return ClientSummary(
            client=client,
            debt_balance=total_balance(debts),
            active_orders_count=sum(1 for o in orders if o.status in _ACTIVE_ORDER_STATUSES),
            open_tasks_count=sum(1 for t in tasks if t.status is not TaskStatus.DONE),
        )
