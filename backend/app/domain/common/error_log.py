from typing import Protocol


class IErrorLog(Protocol):
    """Последние необработанные серверные ошибки — для админ-эндпоинта
    (см. app.infrastructure.observability.admin_alerts), не гарантирует сохранность
    (реализация — Redis, см. app.infrastructure.observability.error_log): запись может
    не дойти при сбое Redis, это диагностика, а не аудит."""

    async def push(self, entry: dict) -> None: ...

    async def list_recent(self, limit: int) -> list[dict]: ...
