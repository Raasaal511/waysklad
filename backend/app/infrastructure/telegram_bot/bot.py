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
from aiogram.exceptions import TelegramNetworkError

from app.infrastructure.config import settings
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.telegram_bot.handlers import router
from app.infrastructure.telegram_bot.storage import PostgresStorage

_logger = logging.getLogger(__name__)


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

    await _delete_webhook(bot)
    await dispatcher.start_polling(bot)


async def _delete_webhook(bot: Bot) -> None:
    """Страховка от 409, если где-то остался webhook. Накопившиеся апдейты не
    выбрасываем: это контакты и /start, отправленные, пока бот лежал, — иначе
    человек «поделился номером», а магазин так и не создан. Telegram недоступен
    — ждём и пробуем снова, а не падаем: падение = рестарт контейнера по кругу."""
    delay = 1.0
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            return
        except TelegramNetworkError:
            _logger.warning("Telegram недоступен, повтор через %.0f с", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
