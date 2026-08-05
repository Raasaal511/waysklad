from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class PeriodTotals:
    sales_count: int
    revenue: Decimal
    profit: Decimal


@dataclass(frozen=True)
class ProductSales:
    product_id: int
    product_name: str
    quantity_sold: Decimal
    revenue: Decimal


@dataclass(frozen=True)
class CategoryProfit:
    category_id: int | None
    category_name: str
    revenue: Decimal
    profit: Decimal


@dataclass(frozen=True)
class DeadStockItem:
    product_id: int
    product_name: str
    quantity: Decimal
    purchase_price: Decimal
    last_sale_at: datetime | None


@dataclass(frozen=True)
class StockValueItem:
    product_id: int
    product_name: str
    quantity: Decimal
    purchase_price: Decimal

    @property
    def value(self) -> Decimal:
        return self.quantity * self.purchase_price


class IAnalyticsRepository(Protocol):
    async def totals_for_period(self, date_from: datetime, date_to: datetime) -> PeriodTotals: ...

    async def top_products(
        self, date_from: datetime, date_to: datetime, limit: int = 10
    ) -> list[ProductSales]: ...

    async def profit_by_category(
        self, date_from: datetime, date_to: datetime
    ) -> list[CategoryProfit]: ...

    async def dead_stock(self, stale_after: date) -> list[DeadStockItem]: ...

    async def stock_value(self) -> list[StockValueItem]: ...

    async def debts_issued_total(self, date_from: datetime, date_to: datetime) -> Decimal: ...
