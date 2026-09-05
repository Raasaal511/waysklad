from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import InsufficientStockError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse
from app.domain.orders.entities import Order, OrderLine, OrderSource


@dataclass(frozen=True)
class OrderItemInput:
    product_id: int
    quantity: Decimal
    price: Decimal
    variant_id: int | None = None


@dataclass(frozen=True)
class CreateOrderCommand:
    client_id: int
    warehouse_id: int
    items: list[OrderItemInput]
    due_date: date | None = None       # дата готовности/выдачи
    prepayment: Decimal = Decimal("0")  # запись о предоплате, не платёж
    source: OrderSource = OrderSource.IN_PERSON
    note: str = ""                      # «из директа», размер, пожелания


class CreateOrderUseCase:
    """Заказ за 30 секунд прямо из переписки WhatsApp/Instagram — резервирует остаток."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateOrderCommand) -> Order:
        require(actor, Permission.ORDERS_MANAGE)
        require_warehouse(actor, cmd.warehouse_id)

        async with self._uow as uow:
            await uow.clients.get(cmd.client_id)  # проверка существования

            lines = []
            for item in cmd.items:
                product = await uow.products.get(item.product_id)
                lines.append(
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

            new_order = Order(
                id=None,
                client_id=cmd.client_id,
                warehouse_id=cmd.warehouse_id,
                lines=lines,
                due_date=cmd.due_date,
                prepayment=Money.of(cmd.prepayment),
                source=cmd.source,
                note=cmd.note,
            )
            new_order.validate()
            order = await uow.orders.add(new_order)
            await uow.clients.link_to_warehouse(order.client_id, order.warehouse_id)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "order.create", order.id,
                    client_id=cmd.client_id, total=str(order.total.amount),
                )
            )
            await uow.commit()
            return order
