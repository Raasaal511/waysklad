from datetime import date, datetime, timezone

from app.domain.analytics.period import SummaryPeriod, period_range
from app.domain.identity.entities import Tenant
from app.infrastructure.telegram import _is_due


def test_day_bounds_is_the_given_day_only():
    rng = period_range(SummaryPeriod.DAY, today=date(2026, 8, 25))
    assert rng.date_from == datetime(2026, 8, 25, tzinfo=timezone.utc)
    assert rng.date_to.date() == date(2026, 8, 26)
    assert (rng.date_to - rng.date_from).days == 1


def test_week_bounds_is_monday_to_next_monday():
    # вторник, 2026-08-25 — неделя должна начаться в понедельник 2026-08-24
    rng = period_range(SummaryPeriod.WEEK, today=date(2026, 8, 25))
    assert rng.date_from.date() == date(2026, 8, 24)
    assert rng.date_to.date() == date(2026, 8, 31)  # следующий понедельник


def test_week_bounds_when_today_is_monday():
    rng = period_range(SummaryPeriod.WEEK, today=date(2026, 8, 24))
    assert rng.date_from.date() == date(2026, 8, 24)
    assert rng.date_to.date() == date(2026, 8, 31)


def test_week_bounds_when_today_is_sunday():
    rng = period_range(SummaryPeriod.WEEK, today=date(2026, 8, 30))
    assert rng.date_from.date() == date(2026, 8, 24)
    assert rng.date_to.date() == date(2026, 8, 31)


def test_month_bounds_is_first_to_next_month_first():
    rng = period_range(SummaryPeriod.MONTH, today=date(2026, 8, 15))
    assert rng.date_from.date() == date(2026, 8, 1)
    assert rng.date_to.date() == date(2026, 9, 1)


def test_month_bounds_handles_february_leap_year():
    rng = period_range(SummaryPeriod.MONTH, today=date(2028, 2, 10))  # 2028 — високосный
    assert rng.date_from.date() == date(2028, 2, 1)
    assert rng.date_to.date() == date(2028, 3, 1)


def test_month_bounds_handles_december():
    rng = period_range(SummaryPeriod.MONTH, today=date(2026, 12, 20))
    assert rng.date_from.date() == date(2026, 12, 1)
    assert rng.date_to.date() == date(2027, 1, 1)


def _tenant(**overrides) -> Tenant:
    fields = dict(
        id=1, name="Тест",
        summary_daily_enabled=True, summary_weekly_enabled=False,
        summary_monthly_enabled=False, summary_daily_hour_msk=20,
    )
    fields.update(overrides)
    return Tenant(**fields)


def test_daily_due_only_at_configured_hour_msk():
    # МСК = UTC+3: владелец хочет 9:00 МСК -> now в UTC должен быть 6:00
    tenant = _tenant(summary_daily_hour_msk=9)
    assert _is_due(tenant, SummaryPeriod.DAY, datetime(2026, 8, 25, 6, tzinfo=timezone.utc))
    assert not _is_due(tenant, SummaryPeriod.DAY, datetime(2026, 8, 25, 9, tzinfo=timezone.utc))


def test_daily_due_false_when_disabled():
    tenant = _tenant(summary_daily_enabled=False, summary_daily_hour_msk=9)
    assert not _is_due(tenant, SummaryPeriod.DAY, datetime(2026, 8, 25, 6, tzinfo=timezone.utc))


def test_weekly_due_when_enabled_regardless_of_hour():
    tenant = _tenant(summary_weekly_enabled=True)
    assert _is_due(tenant, SummaryPeriod.WEEK, datetime(2026, 8, 25, 3, tzinfo=timezone.utc))
    assert _is_due(tenant, SummaryPeriod.WEEK, datetime(2026, 8, 25, 23, tzinfo=timezone.utc))


def test_weekly_due_false_when_disabled():
    tenant = _tenant(summary_weekly_enabled=False)
    assert not _is_due(tenant, SummaryPeriod.WEEK, datetime(2026, 8, 25, tzinfo=timezone.utc))


def test_monthly_due_when_enabled():
    tenant = _tenant(summary_monthly_enabled=True)
    assert _is_due(tenant, SummaryPeriod.MONTH, datetime(2026, 8, 25, tzinfo=timezone.utc))
