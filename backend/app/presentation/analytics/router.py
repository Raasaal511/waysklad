from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter

from app.application.analytics.dead_stock import DeadStockQuery
from app.application.analytics.missed_sales import MissedSalesQuery
from app.application.analytics.period_totals import PeriodTotalsQuery
from app.application.analytics.revenue_timeline import RevenueTimelineQuery
from app.application.analytics.top_products import CategoryProfitQuery, TopProductsQuery
from app.domain.analytics.repository import TimelineBucket
from app.domain.identity.permissions import Permission
from app.presentation.analytics.schemas import (
    CategoryProfitResponse,
    DashboardResponse,
    DeadStockItemResponse,
    MissedSaleResponse,
    PeriodTotalsResponse,
    ProductSalesResponse,
    StockValueResponse,
    TimelinePointResponse,
)
from app.presentation.deps import (
    ActorDep,
    GetCategoryProfitDep,
    GetDashboardDep,
    GetDeadStockDep,
    GetMissedSalesDep,
    GetPeriodTotalsDep,
    GetRevenueTimelineDep,
    GetStockValueDep,
    GetTopProductsDep,
)
from app.presentation.deps.auth import require_permission

router = APIRouter(
    prefix="/analytics", tags=["analytics"],
    dependencies=[require_permission(Permission.ANALYTICS_VIEW)],
)

STALE_DAYS_DEFAULT = 60


def _default_period(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    """По умолчанию — последние 365 дней (страница «Аналитика» открывается за год)."""
    today = datetime.now(timezone.utc).date()
    start = date_from or today - timedelta(days=365)
    end = (date_to or today) + timedelta(days=1)  # включительно
    return (
        datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
        datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc),
    )


@router.get("/dashboard")
async def get_dashboard(actor: ActorDep, use_case: GetDashboardDep) -> DashboardResponse:
    return DashboardResponse.from_result(await use_case.execute(actor))


@router.get("/totals")
async def get_period_totals(
    actor: ActorDep, use_case: GetPeriodTotalsDep,
    date_from: date | None = None, date_to: date | None = None,
) -> PeriodTotalsResponse:
    period_from, period_to = _default_period(date_from, date_to)
    result = await use_case.execute(actor, PeriodTotalsQuery(date_from=period_from, date_to=period_to))
    return PeriodTotalsResponse.from_entity(result)


@router.get("/top-products")
async def get_top_products(
    actor: ActorDep, use_case: GetTopProductsDep,
    date_from: date | None = None, date_to: date | None = None, limit: int = 10,
) -> list[ProductSalesResponse]:
    period_from, period_to = _default_period(date_from, date_to)
    result = await use_case.execute(
        actor, TopProductsQuery(date_from=period_from, date_to=period_to, limit=limit)
    )
    return [ProductSalesResponse.from_entity(item) for item in result]


@router.get("/timeline")
async def get_revenue_timeline(
    actor: ActorDep, use_case: GetRevenueTimelineDep,
    date_from: date | None = None, date_to: date | None = None,
    bucket: TimelineBucket = "month",
) -> list[TimelinePointResponse]:
    period_from, period_to = _default_period(date_from, date_to)
    result = await use_case.execute(
        actor, RevenueTimelineQuery(date_from=period_from, date_to=period_to, bucket=bucket)
    )
    return [TimelinePointResponse.from_entity(item) for item in result]


@router.get("/category-profit")
async def get_category_profit(
    actor: ActorDep, use_case: GetCategoryProfitDep,
    date_from: date | None = None, date_to: date | None = None,
) -> list[CategoryProfitResponse]:
    period_from, period_to = _default_period(date_from, date_to)
    result = await use_case.execute(
        actor, CategoryProfitQuery(date_from=period_from, date_to=period_to)
    )
    return [CategoryProfitResponse.from_entity(item) for item in result]


@router.get("/missed-sales")
async def get_missed_sales(
    actor: ActorDep, use_case: GetMissedSalesDep,
    date_from: date | None = None, date_to: date | None = None,
) -> list[MissedSaleResponse]:
    period_from, period_to = _default_period(date_from, date_to)
    result = await use_case.execute(
        actor, MissedSalesQuery(date_from=period_from, date_to=period_to)
    )
    return [MissedSaleResponse.from_entity(item) for item in result]


@router.get("/dead-stock")
async def get_dead_stock(
    actor: ActorDep, use_case: GetDeadStockDep, stale_days: int = STALE_DAYS_DEFAULT,
) -> list[DeadStockItemResponse]:
    result = await use_case.execute(actor, DeadStockQuery(stale_days=stale_days))
    return [DeadStockItemResponse.from_entity(item) for item in result]


@router.get("/stock-value")
async def get_stock_value(actor: ActorDep, use_case: GetStockValueDep) -> StockValueResponse:
    return StockValueResponse.from_entities(await use_case.execute(actor))
