"""Планировщик фоновых задач для прода — отдельный контейнер (см. docker-compose.prod.yml).

Простой бесконечный цикл вместо системного cron: тот же образ backend,
никаких дополнительных зависимостей и файлов crontab внутри контейнера.

    docker compose -f docker-compose.prod.yml up -d scheduler
"""

import time
import traceback
from datetime import datetime, timezone

from app.application.debts.notify_due_debts import notify_due_debts
from app.infrastructure.telegram import send_daily_summaries

CHECK_INTERVAL_SECONDS = 15 * 60  # уведомления о долгах — раз в 15 минут
SUMMARY_HOUR_UTC = 18  # ежедневная сводка — раз в сутки, в этот час UTC


def _log(message: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def _run_safely(name: str, job) -> None:
    try:
        job()
    except Exception:
        _log(f"{name}: ошибка\n{traceback.format_exc()}")


def main() -> None:
    _log("scheduler: запущен")
    last_summary_date = None
    while True:
        _run_safely("notify_due_debts", notify_due_debts)

        now = datetime.now(timezone.utc)
        if now.hour == SUMMARY_HOUR_UTC and last_summary_date != now.date():
            _run_safely("send_daily_summaries", send_daily_summaries)
            last_summary_date = now.date()

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
