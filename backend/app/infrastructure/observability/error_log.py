"""Последние необработанные ошибки — для GET /api/admin/error-logs.
Redis LPUSH+LTRIM (не растущий лог): фиксированный размер, старые записи
молча вытесняются, никакой БД/миграций ради диагностики."""

import json

from app.domain.common.error_log import IErrorLog
from app.infrastructure.logging import get_logger

_logger = get_logger("app.error_log")
_MAX_ENTRIES = 200


class RedisErrorLog(IErrorLog):
    def __init__(self, redis_url: str, key: str = "admin:error_log") -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        self._key = key

    async def push(self, entry: dict) -> None:
        try:
            await self._redis.lpush(self._key, json.dumps(entry))
            await self._redis.ltrim(self._key, 0, _MAX_ENTRIES - 1)
        except Exception:
            # диагностика не должна сама себя ронять — потерянная запись лога
            # не критична, в отличие от промаха обычного кеша
            _logger.exception("Не удалось записать ошибку в error log (Redis)")

    async def list_recent(self, limit: int) -> list[dict]:
        try:
            raw = await self._redis.lrange(self._key, 0, limit - 1)
        except Exception:
            _logger.exception("Не удалось прочитать error log (Redis)")
            return []
        entries = []
        for item in raw:
            try:
                entries.append(json.loads(item))
            except Exception:
                continue
        return entries
