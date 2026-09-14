from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse
from app.domain.orders.entities import Order, OrderStatus


@dataclass(frozen=True)
class CancelOrderCommand:
    order_id: int
    reason: str = ""


class CancelOrderUseCase:
    """Клиент передумал — освобождает резерв остатка, заказ не восстановить."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CancelOrderCommand) -> Order:
        require(actor, Permission.ORDERS_MANAGE)

        async with self._uow as uow:
            order = await uow.orders.get(cmd.order_id)
            require_warehouse(actor, order.warehouse_id)
            if order.status in (OrderStatus.ISSUED, OrderStatus.CANCELLED):
                raise DomainError(f"Заказ уже «{order.status}» — отмена недоступна")

            for line in order.lines:
                await uow.stock.reserve(
                    line.product_id, order.warehouse_id, -line.quantity.value, line.variant_id
                )

            order.change_status(OrderStatus.CANCELLED)
            if cmd.reason:
                order.note = f"{order.note}\nОтмена: {cmd.reason}".strip()
            await uow.orders.save(order)

            await uow.audit.add(
                AuditEntry.record(actor, "order.cancel", order.id, reason=cmd.reason)
            )
            await uow.commit()
            return order
