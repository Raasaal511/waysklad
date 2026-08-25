"""Границы календарных периодов для сводок — чистые функции, без побочных эффектов.

Неделя — строго понедельник–воскресенье (не скользящее окно 7 дней).
Месяц — строго 1-е число–последний день месяца (не скользящее окно 30 дней).
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum


class SummaryPeriod(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass(frozen=True)
class PeriodRange:
    date_from: datetime
    date_to: datetime  # эксклюзивная верхняя граница


def _day_bounds(today: date) -> tuple[date, date]:
    return today, today + timedelta(days=1)


def _week_bounds(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=7)


def _month_bounds(today: date) -> tuple[date, date]:
    first = today.replace(day=1)
    _, days_in_month = monthrange(today.year, today.month)
    next_first = first + timedelta(days=days_in_month)
    return first, next_first


_BOUNDS = {
    SummaryPeriod.DAY: _day_bounds,
    SummaryPeriod.WEEK: _week_bounds,
    SummaryPeriod.MONTH: _month_bounds,
}


def period_range(period: SummaryPeriod, today: date | None = None) -> PeriodRange:
    today = today or datetime.now(timezone.utc).date()
    start, end = _BOUNDS[period](today)
    return PeriodRange(
        date_from=datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
        date_to=datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc),
    )
