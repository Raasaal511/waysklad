from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.application.analytics.dashboard import DashboardResult
from app.domain.analytics.repository import (
    CategoryProfit,
    DeadStockItem,
    PeriodTotals,
    ProductSales,
    StockValueItem,
    TimelinePoint,
)
from app.domain.common.money import Money


class PeriodTotalsResponse(BaseModel):
    sales_count: int
    revenue: Decimal
    profit: Decimal

    @classmethod
    def from_entity(cls, totals: PeriodTotals) -> "PeriodTotalsResponse":
        return cls(
            sales_count=totals.sales_count,
            revenue=Money.of(totals.revenue).amount,
            profit=Money.of(totals.profit).amount,
        )


class DashboardResponse(BaseModel):
    today: PeriodTotalsResponse
    week: PeriodTotalsResponse
    month: PeriodTotalsResponse

    @classmethod
    def from_result(cls, result: DashboardResult) -> "DashboardResponse":
        return cls(
            today=PeriodTotalsResponse.from_entity(result.today),
            week=PeriodTotalsResponse.from_entity(result.week),
            month=PeriodTotalsResponse.from_entity(result.month),
        )


class TimelinePointResponse(BaseModel):
    bucket_start: date
    sales_count: int
    revenue: Decimal
    profit: Decimal

    @classmethod
    def from_entity(cls, point: TimelinePoint) -> "TimelinePointResponse":
        return cls(
            bucket_start=point.bucket_start,
            sales_count=point.sales_count,
            revenue=Money.of(point.revenue).amount,
            profit=Money.of(point.profit).amount,
        )


class ProductSalesResponse(BaseModel):
    product_id: int
    product_name: str
    quantity_sold: Decimal
    revenue: Decimal

    @classmethod
    def from_entity(cls, item: ProductSales) -> "ProductSalesResponse":
        return cls(
            product_id=item.product_id, product_name=item.product_name,
            quantity_sold=item.quantity_sold, revenue=Money.of(item.revenue).amount,
        )


class CategoryProfitResponse(BaseModel):
    category_id: int | None
    category_name: str
    revenue: Decimal
    profit: Decimal

    @classmethod
    def from_entity(cls, item: CategoryProfit) -> "CategoryProfitResponse":
        return cls(
            category_id=item.category_id, category_name=item.category_name,
            revenue=Money.of(item.revenue).amount, profit=Money.of(item.profit).amount,
        )


class DeadStockItemResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: Decimal
    purchase_price: Decimal
    last_sale_at: datetime | None

    @classmethod
    def from_entity(cls, item: DeadStockItem) -> "DeadStockItemResponse":
        return cls(
            product_id=item.product_id, product_name=item.product_name,
            quantity=item.quantity, purchase_price=Money.of(item.purchase_price).amount,
            last_sale_at=item.last_sale_at,
        )


class StockValueItemResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: Decimal
    purchase_price: Decimal
    value: Decimal

    @classmethod
    def from_entity(cls, item: StockValueItem) -> "StockValueItemResponse":
        return cls(
            product_id=item.product_id, product_name=item.product_name,
            quantity=item.quantity, purchase_price=Money.of(item.purchase_price).amount,
            value=Money.of(item.value).amount,
        )


class StockValueResponse(BaseModel):
    total_value: Decimal
    items: list[StockValueItemResponse]

    @classmethod
    def from_entities(cls, items: list[StockValueItem]) -> "StockValueResponse":
        total = Money.zero()
        for item in items:
            total = total + Money.of(item.value)
        return cls(
            total_value=total.amount,
            items=[StockValueItemResponse.from_entity(item) for item in items],
        )
