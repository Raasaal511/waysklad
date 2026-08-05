"""Уведомления в Telegram + ежевечерняя сводка владельцу.

Запуск сводки по cron на хосте:
    docker compose exec backend python -m app.infrastructure.telegram
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from app.domain.analytics.summary import render_daily_summary
from app.infrastructure.config import settings
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class TelegramNotifier:
    def send(self, chat_id: str, text: str) -> None:
        httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )


async def _send_summaries_async(notifier: TelegramNotifier) -> None:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    async with SqlAlchemyUnitOfWork(None) as uow:
        tenants = await uow.tenants.list_all()

    for tenant in tenants:
        if not tenant.owner_telegram_chat_id:
            continue
        async with SqlAlchemyUnitOfWork(tenant.id) as uow:
            totals = await uow.analytics.totals_for_period(today_start, tomorrow_start)
            debts_issued = await uow.analytics.debts_issued_total(today_start, tomorrow_start)
        text = render_daily_summary(tenant.name, totals, debts_issued)
        notifier.send(tenant.owner_telegram_chat_id, text)


def send_daily_summaries() -> None:
    asyncio.run(_send_summaries_async(TelegramNotifier()))


if __name__ == "__main__":
    send_daily_summaries()
