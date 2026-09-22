from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.application.inventory.common import LineInput
from app.application.inventory.receive_goods import ReceiveGoodsCommand
from app.application.inventory.write_off import WriteOffCommand
from app.application.sales.create_sale import CreateSaleCommand, SaleItemInput
from app.application.sales.return_sale import ReturnItemInput, ReturnSaleCommand
from app.application.sync.apply_offline_ops import (
    ApplyOfflineSalesCommand,
    ApplyOfflineSalesResult,
)
from app.domain.inventory.entities import StockDocument
from app.domain.sales.entities import Sale, SaleReturn
from app.domain.sales.payment import PaymentMethod


class OfflineSaleItemRequest(BaseModel):
    product_id: int
    quantity: Decimal
    price: Decimal
    variant_id: int | None = None


class OfflineSaleRequest(BaseModel):
    client_op_id: str  # обязателен — иначе повторная отправка задвоит продажу
    warehouse_id: int
    payment_method: PaymentMethod
    items: list[OfflineSaleItemRequest]
    discount: Decimal = Decimal("0")
    client_id: int | None = None
    cash_received: Decimal | None = None
    # «долг до» — без этого поля продажа в долг (самый частый способ оплаты
    # в регионе) не могла попасть в офлайн-очередь: CreateSaleUseCase требует
    # debt_due_date при payment_method=CREDIT и раньше просто отклонял такую
    # синхронизацию с ошибкой, вместо того чтобы применить её как остальные.
    debt_due_date: date | None = None
    paid_now: Decimal = Decimal("0")  # отсутствует в старых записях IndexedDB → 0

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
            client_op_id=self.client_op_id,
            debt_due_date=self.debt_due_date,
            paid_now=self.paid_now,
        )


class OfflineReturnItemRequest(BaseModel):
    sale_line_id: int
    quantity: Decimal


class OfflineReturnRequest(BaseModel):
    client_op_id: str
    sale_id: int
    items: list[OfflineReturnItemRequest]
    note: str = ""

    def to_command(self) -> ReturnSaleCommand:
        return ReturnSaleCommand(
            sale_id=self.sale_id,
            items=[
                ReturnItemInput(sale_line_id=item.sale_line_id, quantity=item.quantity)
                for item in self.items
            ],
            note=self.note,
            client_op_id=self.client_op_id,
        )


class OfflineStockLineRequest(BaseModel):
    product_id: int
    quantity: Decimal
    variant_id: int | None = None
    cost: Decimal | None = None


class OfflineReceiptRequest(BaseModel):
    client_op_id: str
    warehouse_id: int
    lines: list[OfflineStockLineRequest]
    note: str = ""
    supplier_id: int | None = None
    debt_due_date: date | None = None

    def to_command(self) -> ReceiveGoodsCommand:
        return ReceiveGoodsCommand(
            warehouse_id=self.warehouse_id,
            lines=[
                LineInput(
                    product_id=line.product_id, quantity=line.quantity,
                    variant_id=line.variant_id, cost=line.cost,
                )
                for line in self.lines
            ],
            note=self.note,
            supplier_id=self.supplier_id,
            debt_due_date=self.debt_due_date,
            client_op_id=self.client_op_id,
        )


class OfflineWriteOffRequest(BaseModel):
    client_op_id: str
    warehouse_id: int
    lines: list[OfflineStockLineRequest]
    note: str = ""

    def to_command(self) -> WriteOffCommand:
        return WriteOffCommand(
            warehouse_id=self.warehouse_id,
            lines=[
                LineInput(
                    product_id=line.product_id, quantity=line.quantity,
                    variant_id=line.variant_id, cost=line.cost,
                )
                for line in self.lines
            ],
            note=self.note,
            client_op_id=self.client_op_id,
        )


class SyncSalesRequest(BaseModel):
    sales: list[OfflineSaleRequest] = []
    returns: list[OfflineReturnRequest] = []
    receipts: list[OfflineReceiptRequest] = []
    writeoffs: list[OfflineWriteOffRequest] = []

    def to_command(self) -> ApplyOfflineSalesCommand:
        return ApplyOfflineSalesCommand(
            sales=[sale.to_command() for sale in self.sales],
            returns=[r.to_command() for r in self.returns],
            receipts=[r.to_command() for r in self.receipts],
            writeoffs=[w.to_command() for w in self.writeoffs],
        )


class AppliedSaleResponse(BaseModel):
    client_op_id: str | None
    id: int
    total: Decimal
    created_at: datetime

    @classmethod
    def from_entity(cls, sale: Sale) -> "AppliedSaleResponse":
        return cls(
            client_op_id=sale.client_op_id, id=sale.id,
            total=sale.total.amount, created_at=sale.created_at,
        )


class AppliedReturnResponse(BaseModel):
    client_op_id: str | None
    id: int
    sale_id: int
    created_at: datetime

    @classmethod
    def from_entity(cls, sale_return: SaleReturn) -> "AppliedReturnResponse":
        return cls(
            client_op_id=sale_return.client_op_id, id=sale_return.id,
            sale_id=sale_return.sale_id, created_at=sale_return.created_at,
        )


class AppliedStockDocumentResponse(BaseModel):
    client_op_id: str | None
    id: int
    number: int | None
    warehouse_id: int

    @classmethod
    def from_entity(cls, document: StockDocument) -> "AppliedStockDocumentResponse":
        return cls(
            client_op_id=document.client_op_id, id=document.id,
            number=document.number, warehouse_id=document.warehouse_id,
        )


class OfflineOpErrorResponse(BaseModel):
    op_type: str
    client_op_id: str | None
    code: str
    message: str


class SyncSalesResponse(BaseModel):
    applied: list[AppliedSaleResponse]
    applied_returns: list[AppliedReturnResponse]
    applied_receipts: list[AppliedStockDocumentResponse]
    applied_writeoffs: list[AppliedStockDocumentResponse]
    errors: list[OfflineOpErrorResponse]

    @classmethod
    def from_result(cls, result: ApplyOfflineSalesResult) -> "SyncSalesResponse":
        return cls(
            applied=[AppliedSaleResponse.from_entity(s) for s in result.applied],
            applied_returns=[
                AppliedReturnResponse.from_entity(r) for r in result.applied_returns
            ],
            applied_receipts=[
                AppliedStockDocumentResponse.from_entity(d) for d in result.applied_receipts
            ],
            applied_writeoffs=[
                AppliedStockDocumentResponse.from_entity(d) for d in result.applied_writeoffs
            ],
            errors=[
                OfflineOpErrorResponse(
                    op_type=e.op_type, client_op_id=e.client_op_id,
                    code=e.code, message=e.message,
                )
                for e in result.errors
            ],
        )
