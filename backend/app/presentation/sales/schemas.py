from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.application.sales.create_sale import (
    CreateSaleCommand,
    CreateSaleResult,
    SaleItemInput,
)
from app.application.sales.edit_sale import EditSaleCommand
from app.application.sales.return_sale import (
    ReturnItemInput,
    ReturnSaleCommand,
    ReturnSaleResult,
)
from app.domain.sales.entities import Sale
from app.domain.sales.payment import PaymentMethod


class SaleItemRequest(BaseModel):
    product_id: int
    quantity: Decimal
    price: Decimal
    variant_id: int | None = None


class SaleCreateRequest(BaseModel):
    warehouse_id: int
    payment_method: PaymentMethod
    items: list[SaleItemRequest]
    discount: Decimal = Decimal("0")
    client_id: int | None = None
    cash_received: Decimal | None = None
    change_kept: Decimal = Decimal("0")  # клиент не забрал (часть) сдачи
    client_op_id: str | None = None  # id операции с устройства — для повтора из офлайн-очереди
    debt_due_date: date | None = None  # «долг до» — обязателен при payment_method=credit

    def to_command(self) -> CreateSaleCommand:
        return CreateSaleCommand(
            warehouse_id=self.warehouse_id,
            payment_method=self.payment_method,
            items=[
                SaleItemInput(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    price=item.price,
                    variant_id=item.variant_id,
                )
                for item in self.items
            ],
            discount=self.discount,
            client_id=self.client_id,
            cash_received=self.cash_received,
            change_kept=self.change_kept,
            client_op_id=self.client_op_id,
            debt_due_date=self.debt_due_date,
        )


class SaleLineResponse(BaseModel):
    id: int
    product_id: int
    variant_id: int | None
    quantity: Decimal
    price: Decimal
    total: Decimal


class SaleResponse(BaseModel):
    id: int
    warehouse_id: int
    seller_id: int
    payment_method: PaymentMethod
    subtotal: Decimal
    discount: Decimal
    prepayment: Decimal  # предоплата, уже полученная раньше (продажа из выдачи заказа)
    total: Decimal
    change: Decimal | None  # сдача, реально выданная на руки
    cash_received: Decimal | None  # сколько внёс клиент наличными
    change_kept: Decimal  # сколько из сдачи клиент не забрал
    client_id: int | None
    created_at: datetime
    note: str
    deleted_at: datetime | None
    order_id: int | None
    lines: list[SaleLineResponse]

    @classmethod
    def from_result(cls, result: CreateSaleResult) -> "SaleResponse":
        return cls._build(result.sale, result.change.amount if result.change else None)

    @classmethod
    def from_entity(cls, sale: Sale) -> "SaleResponse":
        change = None
        if sale.cash_received is not None and sale.cash_received >= sale.total:
            change = sale.change_for(sale.cash_received)
        return cls._build(sale, change.amount if change else None)

    @classmethod
    def _build(cls, sale: Sale, change: Decimal | None) -> "SaleResponse":
        return cls(
            id=sale.id,
            warehouse_id=sale.warehouse_id,
            seller_id=sale.seller_id,
            payment_method=sale.payment_method,
            subtotal=sale.subtotal.amount,
            discount=sale.discount.amount,
            prepayment=sale.prepayment.amount,
            total=sale.total.amount,
            change=change,
            cash_received=sale.cash_received.amount if sale.cash_received is not None else None,
            change_kept=sale.change_kept.amount,
            client_id=sale.client_id,
            created_at=sale.created_at,
            note=sale.note,
            deleted_at=sale.deleted_at,
            order_id=sale.order_id,
            lines=[
                SaleLineResponse(
                    id=line.id,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity.value,
                    price=line.price.amount,
                    total=line.total.amount,
                )
                for line in sale.lines
            ],
        )


class SaleEditRequest(BaseModel):
    client_id: int | None = None
    note: str = ""

    def to_command(self, sale_id: int) -> EditSaleCommand:
        return EditSaleCommand(sale_id=sale_id, client_id=self.client_id, note=self.note)


class ReturnItemRequest(BaseModel):
    sale_line_id: int
    quantity: Decimal


class SaleReturnCreateRequest(BaseModel):
    items: list[ReturnItemRequest]
    note: str = ""

    def to_command(self, sale_id: int) -> ReturnSaleCommand:
        return ReturnSaleCommand(
            sale_id=sale_id,
            items=[
                ReturnItemInput(sale_line_id=item.sale_line_id, quantity=item.quantity)
                for item in self.items
            ],
            note=self.note,
        )


class SaleReturnLineResponse(BaseModel):
    sale_line_id: int
    quantity: Decimal


class SaleReturnResponse(BaseModel):
    id: int
    sale_id: int
    note: str
    refund: Decimal
    created_at: datetime
    lines: list[SaleReturnLineResponse]

    @classmethod
    def from_result(cls, result: ReturnSaleResult) -> "SaleReturnResponse":
        sale_return = result.sale_return
        return cls(
            id=sale_return.id,
            sale_id=sale_return.sale_id,
            note=sale_return.note,
            refund=result.refund.amount,
            created_at=sale_return.created_at,
            lines=[
                SaleReturnLineResponse(sale_line_id=line.sale_line_id, quantity=line.quantity.value)
                for line in sale_return.lines
            ],
        )


class ReceiptResponse(BaseModel):
    text: str
    whatsapp_link: str | None  # None, если у продажи нет клиента с телефоном/WhatsApp


class SalePaymentSummaryResponse(BaseModel):
    count: int
    total: Decimal


class SalesSummaryResponse(BaseModel):
    """Сводка по всем способам оплаты за период — не зависит от фильтра по способу
    оплаты в списке продаж, показывает все варианты одновременно."""

    by_payment_method: dict[str, SalePaymentSummaryResponse]

    @classmethod
    def from_stats(cls, stats: dict[PaymentMethod, tuple[int, Decimal]]) -> "SalesSummaryResponse":
        return cls(
            by_payment_method={
                method.value: SalePaymentSummaryResponse(count=count, total=total)
                for method, (count, total) in stats.items()
            }
        )
