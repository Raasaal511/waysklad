"""Уведомления в Telegram + сводки владельцу (день/неделя/месяц).

Запуск по расписанию — см. app.infrastructure.scheduler (сервис scheduler
в docker-compose.prod.yml). Ручной разовый запуск ежедневной сводки:
    docker compose exec backend python -m app.infrastructure.telegram
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from app.domain.analytics.period import SummaryPeriod, period_range
from app.domain.analytics.repository import PeriodTotals
from app.domain.analytics.summary import render_summary, summary_title
from app.domain.identity.entities import Tenant
from app.domain.sales.entities import Sale
from app.infrastructure.config import settings
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.summary_export import render_summary_xlsx

_PERIOD_FILENAME = {
    SummaryPeriod.DAY: "сводка-за-день.xlsx",
    SummaryPeriod.WEEK: "сводка-за-неделю.xlsx",
    SummaryPeriod.MONTH: "сводка-за-месяц.xlsx",
}

MSK_OFFSET = timedelta(hours=3)  # Россия не переходит на летнее время с 2014 года — фиксированный сдвиг


def _msk_hour(now_utc: datetime) -> int:
    return (now_utc + MSK_OFFSET).hour


class TelegramNotifier:
    def send(self, chat_id: str, text: str) -> None:
        httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )

    def send_document(self, chat_id: str, filename: str, content: bytes, caption: str = "") -> None:
        httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendDocument",
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (filename, content)},
            timeout=20,
        )


async def _send_summary_for_tenant(
    tenant: Tenant, period: SummaryPeriod, notifier: TelegramNotifier
) -> None:
    if not tenant.owner_telegram_chat_id:
        return

    rng = period_range(period)
    async with SqlAlchemyUnitOfWork(tenant.id) as uow:
        totals = await uow.analytics.totals_for_period(rng.date_from, rng.date_to)
        debts_issued = await uow.analytics.debts_issued_total(rng.date_from, rng.date_to)
        top_products = await uow.analytics.top_products(rng.date_from, rng.date_to, limit=100000)
        debts, _ = await uow.debts.list_filtered(
            {
                "issued_at__gte": rng.date_from.date(),
                "issued_at__lte": rng.date_to.date() - timedelta(days=1),
                "limit": 200,
            }
        )
        clients = await uow.clients.search("", include_inactive=True)
        suppliers = await uow.suppliers.list()
        warehouses = await uow.warehouses.list()
        products = await uow.products.search_all()
        sellers = await uow.users.list_by_tenant()
        sales, _ = await uow.sales.list(
            date_from=rng.date_from.date(),
            date_to=rng.date_to.date() - timedelta(days=1),
            limit=100000,
        )

        by_warehouse: list[tuple[str, PeriodTotals]] = []
        if len(warehouses) > 1:
            for warehouse in warehouses:
                w_totals = await uow.analytics.totals_for_period(
                    rng.date_from, rng.date_to, warehouse_ids=[warehouse.id]
                )
                by_warehouse.append((warehouse.name, w_totals))

    counterparty_name = {("client", c.id): c.name for c in clients}
    counterparty_name.update({("supplier", s.id): s.name for s in suppliers})
    product_name = {p.id: p.name for p in products}
    product_fractional = {p.id: p.unit.fractional for p in products}
    seller_name = {u.id: u.name for u in sellers}
    warehouse_name = {w.id: w.name for w in warehouses}
    client_name = {c.id: c.name for c in clients}

    text = render_summary(tenant.name, period, totals, debts_issued)
    notifier.send(tenant.owner_telegram_chat_id, text)

    xlsx = render_summary_xlsx(
        tenant.name,
        summary_title(tenant.name, period),
        totals,
        debts_issued,
        top_products,
        debts,
        counterparty_name,
        by_warehouse,
        sales,
        product_name,
        product_fractional,
        seller_name,
        warehouse_name,
        client_name,
    )
    notifier.send_document(tenant.owner_telegram_chat_id, _PERIOD_FILENAME[period], xlsx)


def _is_due(tenant: Tenant, period: SummaryPeriod, now: datetime) -> bool:
    if period is SummaryPeriod.DAY:
        return tenant.summary_daily_enabled and _msk_hour(now) == tenant.summary_daily_hour_msk
    if period is SummaryPeriod.WEEK:
        return tenant.summary_weekly_enabled
    return tenant.summary_monthly_enabled


async def _send_summaries_async(
    period: SummaryPeriod, notifier: TelegramNotifier, now: datetime | None = None
) -> None:
    now = now or datetime.now(timezone.utc)
    async with SqlAlchemyUnitOfWork(None) as uow:
        tenants = await uow.tenants.list_all()

    for tenant in tenants:
        if not _is_due(tenant, period, now):
            continue
        await _send_summary_for_tenant(tenant, period, notifier)


def send_summaries_for(period: SummaryPeriod, now: datetime | None = None) -> None:
    """Для планировщика — шлёт только тем tenant'ам, у кого сейчас наступило их время."""
    asyncio.run(_send_summaries_async(period, TelegramNotifier(), now))


async def _send_daily_summaries_async(notifier: TelegramNotifier) -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        tenants = await uow.tenants.list_all()
    for tenant in tenants:
        if not tenant.summary_daily_enabled:
            continue
        await _send_summary_for_tenant(tenant, SummaryPeriod.DAY, notifier)


def send_daily_summaries() -> None:
    """Ручной разовый запуск ежедневной сводки — без проверки часа."""
    asyncio.run(_send_daily_summaries_async(TelegramNotifier()))


if __name__ == "__main__":
    send_daily_summaries()
