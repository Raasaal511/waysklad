from decimal import Decimal

from app.domain.analytics.repository import PeriodTotals


def render_daily_summary(shop_name: str, totals: PeriodTotals, debts_issued: Decimal) -> str:
    return (
        f"{shop_name} — сводка за сегодня\n"
        f"Продаж: {totals.sales_count}\n"
        f"Выручка: {totals.revenue} ₽\n"
        f"Прибыль: {totals.profit} ₽\n"
        f"Выдано в долг: {debts_issued} ₽"
    )
