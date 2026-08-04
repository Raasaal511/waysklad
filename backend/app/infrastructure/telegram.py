"""Уведомления в Telegram + ежевечерняя сводка владельцу.

Запуск сводки по cron на хосте:
    docker compose exec backend python -m app.infrastructure.telegram
"""

import httpx

from app.infrastructure.config import settings


class TelegramNotifier:
    def send(self, chat_id: str, text: str) -> None:
        httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )


def send_daily_summaries() -> None:
    # TODO (неделя 9): по каждому tenant собрать сводку из application/analytics
    # «Сегодня: 47 продаж, выручка 63 200 ₽, прибыль ~18 400 ₽, долгов выдано 5 000 ₽»
    raise NotImplementedError


if __name__ == "__main__":
    send_daily_summaries()
