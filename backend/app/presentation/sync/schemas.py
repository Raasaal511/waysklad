from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.application.sales.create_sale import CreateSaleCommand, SaleItemInput
from app.application.sync.apply_offline_ops import ApplyOfflineSalesCommand, ApplyOfflineSalesResult
from app.domain.sales.entities import Sale
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
        )


class SyncSalesRequest(BaseModel):
    sales: list[OfflineSaleRequest]

    def to_command(self) -> ApplyOfflineSalesCommand:
        return ApplyOfflineSalesCommand(sales=[sale.to_command() for sale in self.sales])


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


class OfflineOpErrorResponse(BaseModel):
    client_op_id: str | None
    message: str


class SyncSalesResponse(BaseModel):
    applied: list[AppliedSaleResponse]
    errors: list[OfflineOpErrorResponse]

    @classmethod
    def from_result(cls, result: ApplyOfflineSalesResult) -> "SyncSalesResponse":
        return cls(
            applied=[AppliedSaleResponse.from_entity(s) for s in result.applied],
            errors=[
                OfflineOpErrorResponse(client_op_id=e.client_op_id, message=e.message)
                for e in result.errors
            ],
        )
