from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.application.orders.change_status import ChangeOrderStatusCommand
from app.application.orders.create_order import CreateOrderCommand, OrderItemInput
from app.domain.orders.entities import Order, OrderStatus


class OrderItemRequest(BaseModel):
    product_id: int
    quantity: Decimal
    price: Decimal
    variant_id: int | None = None


class OrderCreateRequest(BaseModel):
    client_id: int
    items: list[OrderItemRequest]
    due_date: date | None = None
    prepayment: Decimal = Decimal("0")
    note: str = ""

    def to_command(self) -> CreateOrderCommand:
        return CreateOrderCommand(
            client_id=self.client_id,
            items=[
                OrderItemInput(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    price=item.price,
                    variant_id=item.variant_id,
                )
                for item in self.items
            ],
            due_date=self.due_date,
            prepayment=self.prepayment,
            note=self.note,
        )


class ChangeStatusRequest(BaseModel):
    new_status: OrderStatus

    def to_command(self, order_id: int) -> ChangeOrderStatusCommand:
        return ChangeOrderStatusCommand(order_id=order_id, new_status=self.new_status)


class OrderLineResponse(BaseModel):
    product_id: int
    variant_id: int | None
    quantity: Decimal
    price: Decimal
    total: Decimal


class OrderResponse(BaseModel):
    id: int
    client_id: int
    status: OrderStatus
    total: Decimal
    prepayment: Decimal
    to_pay: Decimal
    due_date: date | None
    note: str
    lines: list[OrderLineResponse]

    @classmethod
    def from_entity(cls, order: Order) -> "OrderResponse":
        return cls(
            id=order.id,
            client_id=order.client_id,
            status=order.status,
            total=order.total.amount,
            prepayment=order.prepayment.amount,
            to_pay=order.to_pay.amount,
            due_date=order.due_date,
            note=order.note,
            lines=[
                OrderLineResponse(
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity.value,
                    price=line.price.amount,
                    total=line.total.amount,
                )
                for line in order.lines
            ],
        )
