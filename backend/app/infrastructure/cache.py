"""Промах после retry (например, Redis сейчас перезапускается) не бросает
исключение наружу — вызывающий use case читает из БД, как при обычном промахе.
"""

from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.retry import Retry

from app.domain.common.cache import ICache
from app.infrastructure.logging import get_logger

_logger = get_logger("app.cache")


class RedisCache(ICache):
    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(
            redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
            retry=Retry(ExponentialBackoff(cap=1, base=0.05), retries=3),
            retry_on_error=[RedisConnectionError, RedisTimeoutError],
        )

    async def get(self, key: str) -> bytes | None:
        try:
            return await self._redis.get(key)
        except Exception:
            _logger.exception("Redis GET не удался, считаем промахом кеша key=%s", key)
            return None

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        try:
            await self._redis.set(key, value, ex=ttl_seconds)
        except Exception:
            _logger.exception("Redis SET не удался — значение просто не закешировалось key=%s", key)

    async def delete_prefix(self, prefix: str) -> None:
        try:
            # SCAN, не KEYS — не блокирует Redis на большой базе ключей
            keys = [key async for key in self._redis.scan_iter(match=f"{prefix}*")]
            if keys:
                await self._redis.delete(*keys)
        except Exception:
            # неудалённые ключи просто доживут до TTL — устаревание, не поломка
            _logger.exception("Redis SCAN/DEL по префиксу не удался prefix=%s", prefix)
