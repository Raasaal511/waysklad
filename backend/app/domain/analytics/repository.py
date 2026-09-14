from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol

TimelineBucket = Literal["day", "week", "month"]


@dataclass(frozen=True)
class PeriodTotals:
    sales_count: int
    revenue: Decimal
    profit: Decimal
    # невзятая клиентами сдача — отдельно от revenue/profit (не выручка по
    # товарам, добровольная доплата сверх цены), см. Sale.change_kept
    change_kept: Decimal = Decimal("0")


@dataclass(frozen=True)
class TimelinePoint:
    bucket_start: date
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
class RestockRecommendation:
    product_id: int
    product_name: str
    quantity: Decimal  # текущий остаток (на переданных складах)
    min_stock: Decimal
    quantity_sold: Decimal  # продано за период (см. RestockRecommendationsUseCase)


@dataclass(frozen=True)
class MissedSaleItem:
    """Товар, которого не хватило хотя бы на одну позицию заявки с витрины —
    покупатель хотел купить, но остатка не было (см. StorefrontRequest.
    insufficient_stock_at_request). Точность на уровне заявки, не строки:
    флаг общий для всей заявки, поэтому quantity_requested — это сумма
    запрошенного по этому товару во ВСЕХ заявках с этим флагом, а не только
    в тех строках, которых реально не хватило."""

    product_id: int
    product_name: str
    requests_count: int
    quantity_requested: Decimal


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
    # warehouse_ids: None — без ограничения (owner/analyst), список — фильтр
    # по складам актора (manager/seller/storekeeper)
    async def totals_for_period(
        self, date_from: datetime, date_to: datetime, warehouse_ids: list[int] | None = None
    ) -> PeriodTotals: ...

    async def revenue_timeline(
        self,
        date_from: datetime,
        date_to: datetime,
        bucket: TimelineBucket,
        warehouse_ids: list[int] | None = None,
    ) -> list[TimelinePoint]:
        """Выручка/прибыль, сгруппированные по бакетам времени (день/неделя/месяц) —
        для графика на странице «Аналитика». Бакеты без продаж не включаются в
        результат (заполняются нулями на вызывающей стороне при необходимости)."""
        ...

    async def top_products(
        self,
        date_from: datetime,
        date_to: datetime,
        limit: int = 10,
        warehouse_ids: list[int] | None = None,
    ) -> list[ProductSales]: ...

    async def profit_by_category(
        self, date_from: datetime, date_to: datetime, warehouse_ids: list[int] | None = None
    ) -> list[CategoryProfit]: ...

    async def dead_stock(
        self, stale_after: date, warehouse_ids: list[int] | None = None
    ) -> list[DeadStockItem]: ...

    async def stock_value(self, warehouse_ids: list[int] | None = None) -> list[StockValueItem]: ...

    async def restock_recommendations(
        self, sale_period_from: datetime, warehouse_ids: list[int] | None = None
    ) -> list[RestockRecommendation]:
        """Товары с остатком <= min_stock, которые при этом продавались с sale_period_from —
        значит их раскупают, а не просто забыли. Сортировка — по проданному, сначала ходовые."""
        ...

    async def debts_issued_total(self, date_from: datetime, date_to: datetime) -> Decimal: ...

    async def missed_sales(
        self, date_from: datetime, date_to: datetime
    ) -> list[MissedSaleItem]:
        """Товары из заявок с витрины (StorefrontRequest), где на момент заявки
        не хватило остатка хотя бы на одну позицию — сортировка по числу таких
        заявок, сначала самые частые. Без фильтра по складам: заявка с витрины
        не привязана к складу до принятия владельцем."""
        ...

    async def sold_count_by_products(self, product_ids: list[int]) -> dict[int, Decimal]:
        """Суммарно продано (SaleLine.quantity за вычетом SaleReturnLine.quantity)
        по каждому из product_ids за всё время — тот же смысл и та же формула,
        что и quantity_sold в top_products (полностью удалённые продажи
        исключены), но без ограничения периода и batch по списку товаров
        (для бейджа «Продано: N» на карточке/списке витрины). Товары без единой
        продажи в результирующем словаре отсутствуют (не 0)."""
        ...
