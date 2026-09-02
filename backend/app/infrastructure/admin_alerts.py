"""Алерт разработчику/оператору при непредвиденной серверной ошибке —
не путать с app.infrastructure.telegram (сводки владельцам магазинов)."""

from app.infrastructure.config import settings
from app.infrastructure.logging import get_logger
from app.infrastructure.telegram import TelegramNotifier

_logger = get_logger("app.errors")
_notifier = TelegramNotifier()


def report_unhandled_error(method: str, path: str, exc: BaseException) -> None:
    _logger.exception("Unhandled error on %s %s", method, path, exc_info=exc)
    if not settings.admin_alert_chat_id or not settings.telegram_bot_token:
        return
    text = (
        f"⚠️ Ошибка на сервере\n"
        f"{method} {path}\n"
        f"{type(exc).__name__}: {exc}"
    )
    try:
        _notifier.send(settings.admin_alert_chat_id, text[:4000])
    except Exception:
        _logger.exception("Не удалось отправить алерт об ошибке в Telegram")
