from app.domain.analytics.period import SummaryPeriod
from app.domain.analytics.repository import PeriodTotals
from app.domain.common.money import format_rub


_PERIOD_TITLE = {
    SummaryPeriod.DAY: "сводка за сегодня",
    SummaryPeriod.WEEK: "сводка за неделю",
    SummaryPeriod.MONTH: "сводка за месяц",
}

_PERIOD_EMOJI = {
    SummaryPeriod.DAY: "📊",
    SummaryPeriod.WEEK: "🗓",
    SummaryPeriod.MONTH: "📅",
}


def summary_title(shop_name: str, period: SummaryPeriod) -> str:
    """Заголовок без HTML-разметки — для Excel и других мест, где теги не нужны."""
    return f"{shop_name} — {_PERIOD_TITLE[period]}"


def render_daily_summary(shop_name: str, totals: PeriodTotals, debts_issued) -> str:
    return render_summary(shop_name, SummaryPeriod.DAY, totals, debts_issued)


def render_summary(
    shop_name: str, period: SummaryPeriod, totals: PeriodTotals, debts_issued
) -> str:
    """HTML-разметка для Telegram (parse_mode=HTML) — жирные цифры, эмодзи-иконки."""
    return (
        f"{_PERIOD_EMOJI[period]} <b>{shop_name}</b> — {_PERIOD_TITLE[period]}\n\n"
        f"📦 Продаж: <b>{totals.sales_count}</b>\n"
        f"💰 Выручка: <b>{format_rub(totals.revenue)}</b>\n"
        f"📈 Прибыль: <b>{format_rub(totals.profit)}</b>\n"
        f"🤝 Выдано в долг: <b>{format_rub(debts_issued)}</b>"
    )
