"""Telegram-бот витрины ВайСклад — один общий бот на все магазины, покупатель
открывает конкретный магазин через deep-link t.me/<bot>?start=<slug> и
проходит каталог → карточка товара → количество → контакты → заявка внутри
чата, без выхода в браузер. Переиспользует те же use case, что и веб-витрина
(GetStorefrontCatalogUseCase, GetStorefrontProductUseCase,
CreateStorefrontRequestUseCase) — никакой отдельной бизнес-логики здесь нет.

Long polling, не webhook — не нужен публичный HTTPS-адрес для MVP.

Запуск (отдельный вечноживущий процесс, см. сервис `storefront_bot` в
docker-compose.yml/docker-compose.prod.yml):
    docker compose exec backend python -m app.infrastructure.telegram_bot.bot
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.infrastructure.config import settings
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.telegram_bot.handlers import router
from app.infrastructure.telegram_bot.storage import PostgresStorage


async def _run() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN не задан — бот витрины не может запуститься без токена"
        )

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dispatcher = Dispatcher(storage=PostgresStorage(SessionLocal), session_factory=SessionLocal)
    dispatcher.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)  # страховка от 409, если где-то остался webhook
    await dispatcher.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
