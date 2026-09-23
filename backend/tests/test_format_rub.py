from decimal import Decimal

from app.domain.analytics.period import SummaryPeriod
from app.domain.analytics.repository import PeriodTotals
from app.domain.analytics.summary import render_summary
from app.domain.common.money import Money, format_rub

NBSP = "\u202f"


def test_format_rub_integers_and_kopecks():
    assert format_rub(0) == "0 ₽"
    assert format_rub(63200) == f"63{NBSP}200 ₽"
    assert format_rub("1250.5") == f"1{NBSP}250,50 ₽"
    assert format_rub(Decimal("1000000")) == f"1{NBSP}000{NBSP}000 ₽"
    assert format_rub(Money.of("-1500.25")) == f"-1{NBSP}500,25 ₽"
    assert format_rub(Money.of("10.00")) == "10 ₽"


def test_render_summary_uses_grouped_rubles():
    totals = PeriodTotals(
        sales_count=3,
        revenue=Decimal("63200"),
        profit=Decimal("1250.5"),
    )
    text = render_summary("Беркат", SummaryPeriod.DAY, totals, Decimal("3000"))
    assert f"63{NBSP}200 ₽" in text
    assert f"1{NBSP}250,50 ₽" in text
    assert f"3{NBSP}000 ₽" in text
    assert "63200.00" not in text
