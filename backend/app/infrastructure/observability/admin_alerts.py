"""Алерт разработчику/оператору при непредвиденной серверной ошибке —
не путать с app.infrastructure.notifications.telegram (сводки владельцам магазинов)."""

from datetime import UTC, datetime

from app.infrastructure.config import settings
from app.infrastructure.notifications.telegram import TelegramNotifier
from app.infrastructure.observability.logging import get_logger

_logger = get_logger("app.errors")
_notifier = TelegramNotifier()
error_log = None
if settings.cache_redis_url:
    from app.infrastructure.observability.error_log import RedisErrorLog

    error_log = RedisErrorLog(settings.cache_redis_url)


def _safe_message(exc: BaseException) -> str:
    """Короткое сообщение без чувствительных деталей (SQL-текст с
    параметрами запроса, соединения БД/Redis и т.п.) — уходит в лог ошибок
    админ-панели, Telegram-алерт и Redis. Полный traceback с полными
    деталями остаётся только в _logger.exception ниже (серверные файлы
    логов, недоступные через веб)."""
    # ленивый импорт — эти пакеты не всегда установлены/нужны на старте
    try:
        import sqlalchemy.exc as sa_exc
        if isinstance(exc, sa_exc.SQLAlchemyError):
            return "Ошибка базы данных"
    except ImportError:
        pass
    try:
        import redis.exceptions as redis_exc
        if isinstance(exc, redis_exc.RedisError):
            return "Ошибка соединения с Redis"
    except ImportError:
        pass
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return "Ошибка соединения"
    return str(exc)[:200]


async def report_unhandled_error(method: str, path: str, exc: BaseException) -> None:
    _logger.exception("Unhandled error on %s %s", method, path, exc_info=exc)

    safe_message = _safe_message(exc)

    if error_log is not None:
        await error_log.push(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "method": method,
                "path": path,
                "error_type": type(exc).__name__,
                "message": safe_message,
            }
        )

    if not settings.admin_alert_chat_id or not settings.telegram_bot_token:
        return
    text = (
        f"⚠️ Ошибка на сервере\n"
        f"{method} {path}\n"
        f"{type(exc).__name__}: {safe_message}"
    )
    try:
        _notifier.send(settings.admin_alert_chat_id, text[:4000])
    except Exception:
        _logger.exception("Не удалось отправить алерт об ошибке в Telegram")
