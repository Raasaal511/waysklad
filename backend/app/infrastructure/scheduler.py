"""Планировщик фоновых задач для прода — отдельный контейнер (см. docker-compose.prod.yml).

Простой бесконечный цикл вместо системного cron: тот же образ backend,
никаких дополнительных зависимостей и файлов crontab внутри контейнера.

    docker compose -f docker-compose.prod.yml up -d scheduler
"""

import time
import traceback
from calendar import monthrange
from datetime import datetime, timezone

from app.application.customers.cleanup_login_links import cleanup_customer_login_links
from app.application.debts.notify_due_debts import notify_due_debts
from app.application.inventory.notify_low_stock import notify_low_stock
from app.application.storefront.release_expired_reservations import (
    release_expired_storefront_reservations,
)
from app.domain.analytics.period import SummaryPeriod
from app.infrastructure.notifications.telegram import MSK_OFFSET, send_summaries_for

CHECK_INTERVAL_SECONDS = 15 * 60  # проверка — раз в 15 минут

# ежедневная сводка шлётся в час, настроенный владельцем per-tenant (Tenant.summary_daily_hour_msk);
# неделя/месяц — фиксированное время по МСК для всех подписанных, чтобы не плодить лишние настройки
WEEKLY_HOUR_MSK = 20  # воскресенье
MONTHLY_HOUR_MSK = 20  # последний день месяца


def _log(message: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def _run_safely(name: str, job) -> None:
    try:
        job()
    except Exception:
        _log(f"{name}: ошибка\n{traceback.format_exc()}")


def _is_last_day_of_month(today) -> bool:
    return today.day == monthrange(today.year, today.month)[1]


def main() -> None:
    _log("scheduler: запущен")
    sent_hours: set[tuple[str, str]] = set()  # (period, "YYYY-MM-DD-HH") — защита от повтора в тот же час
    while True:
        _run_safely("notify_due_debts", notify_due_debts)
        _run_safely("notify_low_stock", notify_low_stock)

        now = datetime.now(timezone.utc)
        now_msk = now + MSK_OFFSET
        hour_key = now.strftime("%Y-%m-%d-%H")
        sent_hours = {k for k in sent_hours if k[1] == hour_key}  # забыть прошлые часы

        if ("storefront_reservations", hour_key) not in sent_hours:
            _run_safely("release_expired_storefront_reservations", release_expired_storefront_reservations)
            sent_hours.add(("storefront_reservations", hour_key))

        if ("customer_login_links", hour_key) not in sent_hours:
            _run_safely("cleanup_customer_login_links", cleanup_customer_login_links)
            sent_hours.add(("customer_login_links", hour_key))

        if (SummaryPeriod.DAY, hour_key) not in sent_hours:
            _run_safely("send_summaries[day]", lambda: send_summaries_for(SummaryPeriod.DAY, now))
            sent_hours.add((SummaryPeriod.DAY, hour_key))

        if now_msk.weekday() == 6 and now_msk.hour == WEEKLY_HOUR_MSK:
            if (SummaryPeriod.WEEK, hour_key) not in sent_hours:
                _run_safely("send_summaries[week]", lambda: send_summaries_for(SummaryPeriod.WEEK, now))
                sent_hours.add((SummaryPeriod.WEEK, hour_key))

        if _is_last_day_of_month(now_msk.date()) and now_msk.hour == MONTHLY_HOUR_MSK:
            if (SummaryPeriod.MONTH, hour_key) not in sent_hours:
                _run_safely("send_summaries[month]", lambda: send_summaries_for(SummaryPeriod.MONTH, now))
                sent_hours.add((SummaryPeriod.MONTH, hour_key))

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
