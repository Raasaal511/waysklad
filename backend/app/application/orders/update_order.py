from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.orders.create_order import OrderItemInput
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError, InsufficientStockError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse
from app.domain.orders.entities import Order, OrderLine, OrderSource, OrderStatus


@dataclass(frozen=True)
class UpdateOrderCommand:
    order_id: int
    client_id: int
    warehouse_id: int
    items: list[OrderItemInput]
    due_date: date | None = None
    prepayment: Decimal = Decimal("0")
    source: OrderSource = OrderSource.IN_PERSON
    note: str = ""


class UpdateOrderUseCase:
    """Редактирование состава/условий, пока заказ не выдан/отменён — резерв
    остатка пересчитывается: старый снимается, новый накладывается заново."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: UpdateOrderCommand) -> Order:
        require(actor, Permission.ORDERS_MANAGE)
        require_warehouse(actor, cmd.warehouse_id)

        async with self._uow as uow:
            order = await uow.orders.get(cmd.order_id)
            if order.status in (OrderStatus.ISSUED, OrderStatus.CANCELLED):
                raise DomainError(f"Заказ уже «{order.status}» — редактирование недоступно")
            require_warehouse(actor, order.warehouse_id)

            await uow.clients.get(cmd.client_id)  # проверка существования

            for line in order.lines:
                await uow.stock.reserve(
                    line.product_id, order.warehouse_id, -line.quantity.value, line.variant_id
                )

            new_lines = []
            for item in cmd.items:
                product = await uow.products.get(item.product_id)
                new_lines.append(
                    OrderLine(
                        product_id=item.product_id,
                        variant_id=item.variant_id,
                        quantity=Quantity(item.quantity, product.unit),
                        price=Money.of(item.price),
                    )
                )
                new_reserved = await uow.stock.reserve(
                    item.product_id, cmd.warehouse_id, item.quantity, item.variant_id
                )
                on_hand = await uow.stock.get(item.product_id, cmd.warehouse_id, item.variant_id)
                if new_reserved > on_hand:
                    raise InsufficientStockError(f"Недостаточно остатка: {product.name}")

            order.client_id = cmd.client_id
            order.warehouse_id = cmd.warehouse_id
            order.lines = new_lines
            order.due_date = cmd.due_date
            order.prepayment = Money.of(cmd.prepayment)
            order.source = cmd.source
            order.note = cmd.note
            order.validate()

            await uow.orders.save(order)
            await uow.audit.add(
                AuditEntry.record(actor, "order.update", order.id, total=str(order.total.amount))
            )
            await uow.commit()
            return order
