from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.application.orders.cancel_order import CancelOrderCommand
from app.application.orders.change_status import ChangeOrderStatusCommand
from app.application.orders.create_order import CreateOrderCommand, OrderItemInput
from app.application.orders.issue_order import IssueOrderCommand, IssueOrderResult
from app.application.orders.update_order import UpdateOrderCommand
from app.domain.orders.entities import Order, OrderSource, OrderStatus
from app.domain.sales.payment import PaymentMethod
from app.presentation.sales.schemas import SaleResponse


class OrderItemRequest(BaseModel):
    product_id: int
    quantity: Decimal
    price: Decimal
    variant_id: int | None = None


class OrderCreateRequest(BaseModel):
    client_id: int
    warehouse_id: int
    items: list[OrderItemRequest]
    due_date: date | None = None
    prepayment: Decimal = Decimal("0")
    source: OrderSource = OrderSource.IN_PERSON
    note: str = ""

    def to_command(self) -> CreateOrderCommand:
        return CreateOrderCommand(
            client_id=self.client_id,
            warehouse_id=self.warehouse_id,
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
            source=self.source,
            note=self.note,
        )


class OrderUpdateRequest(BaseModel):
    client_id: int
    warehouse_id: int
    items: list[OrderItemRequest]
    due_date: date | None = None
    prepayment: Decimal = Decimal("0")
    source: OrderSource = OrderSource.IN_PERSON
    note: str = ""

    def to_command(self, order_id: int) -> UpdateOrderCommand:
        return UpdateOrderCommand(
            order_id=order_id,
            client_id=self.client_id,
            warehouse_id=self.warehouse_id,
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
            source=self.source,
            note=self.note,
        )


class ChangeStatusRequest(BaseModel):
    new_status: OrderStatus

    def to_command(self, order_id: int) -> ChangeOrderStatusCommand:
        return ChangeOrderStatusCommand(order_id=order_id, new_status=self.new_status)


class CancelOrderRequest(BaseModel):
    reason: str = ""

    def to_command(self, order_id: int) -> CancelOrderCommand:
        return CancelOrderCommand(order_id=order_id, reason=self.reason)


class IssueOrderRequest(BaseModel):
    payment_method: PaymentMethod
    cash_received: Decimal | None = None
    change_kept: Decimal = Decimal("0")  # клиент не забрал (часть) сдачи
    debt_due_date: date | None = None

    def to_command(self, order_id: int) -> IssueOrderCommand:
        return IssueOrderCommand(
            order_id=order_id,
            payment_method=self.payment_method,
            cash_received=self.cash_received,
            change_kept=self.change_kept,
            debt_due_date=self.debt_due_date,
        )


class OrderLineResponse(BaseModel):
    product_id: int
    variant_id: int | None
    quantity: Decimal
    price: Decimal
    total: Decimal


class OrderResponse(BaseModel):
    id: int
    number: int | None
    client_id: int
    warehouse_id: int
    status: OrderStatus
    source: OrderSource
    total: Decimal
    prepayment: Decimal
    to_pay: Decimal
    due_date: date | None
    note: str
    sale_id: int | None
    created_at: datetime | None
    lines: list[OrderLineResponse]

    @classmethod
    def from_entity(cls, order: Order) -> "OrderResponse":
        return cls(
            id=order.id,
            number=order.number,
            client_id=order.client_id,
            warehouse_id=order.warehouse_id,
            status=order.status,
            source=order.source,
            total=order.total.amount,
            prepayment=order.prepayment.amount,
            to_pay=order.to_pay.amount,
            due_date=order.due_date,
            note=order.note,
            sale_id=order.sale_id,
            created_at=order.created_at,
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


class IssueOrderResponse(BaseModel):
    order: OrderResponse
    sale: SaleResponse

    @classmethod
    def from_result(cls, result: IssueOrderResult) -> "IssueOrderResponse":
        return cls(
            order=OrderResponse.from_entity(result.order),
            sale=SaleResponse.from_entity(result.sale),
        )
