from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.application.sales.create_sale import (
    CreateSaleCommand,
    CreateSaleResult,
    SaleItemInput,
)
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
        )


class SaleLineResponse(BaseModel):
    product_id: int
    variant_id: int | None
    quantity: Decimal
    price: Decimal
    total: Decimal


class SaleResponse(BaseModel):
    id: int
    payment_method: PaymentMethod
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    change: Decimal | None  # сдача
    client_id: int | None
    created_at: datetime
    lines: list[SaleLineResponse]

    @classmethod
    def from_result(cls, result: CreateSaleResult) -> "SaleResponse":
        sale = result.sale
        return cls(
            id=sale.id,
            payment_method=sale.payment_method,
            subtotal=sale.subtotal.amount,
            discount=sale.discount.amount,
            total=sale.total.amount,
            change=result.change.amount if result.change else None,
            client_id=sale.client_id,
            created_at=sale.created_at,
            lines=[
                SaleLineResponse(
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity.value,
                    price=line.price.amount,
                    total=line.total.amount,
                )
                for line in sale.lines
            ],
        )
