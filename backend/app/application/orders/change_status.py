from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.orders.entities import Order, OrderStatus


@dataclass(frozen=True)
class ChangeOrderStatusCommand:
    order_id: int
    new_status: OrderStatus


class ChangeOrderStatusUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ChangeOrderStatusCommand) -> Order:
        require(actor, Permission.ORDERS_MANAGE)

        async with self._uow as uow:
            order = await uow.orders.get(cmd.order_id)
            order.change_status(cmd.new_status)  # домен проверит допустимость перехода
            await uow.orders.save(order)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "order.status", order.id, status=cmd.new_status.value
                )
            )
            await uow.commit()
            return order
