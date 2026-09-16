"""История нагрузки сервера за последний час — точки сэмплируются прямо на
чтении (GET /api/admin/status), не отдельным фоновым процессом: страница
статуса и так опрашивается с фронта раз в 8 сек, пока кто-то на неё смотрит,
throttling ниже просто прореживает эти вызовы до одной точки в SAMPLE_INTERVAL_SECONDS.

Redis LPUSH+LTRIM — тот же паттерн, что error_log.py (фиксированный размер,
старые точки молча вытесняются, без БД/миграций ради диагностики)."""

import json
import time

from app.domain.common.metrics_history import IMetricsHistory
from app.infrastructure.config import settings
from app.infrastructure.observability.logging import get_logger

_logger = get_logger("app.metrics_history")
_MAX_POINTS = 120  # с шагом в минуту — 2 часа истории, с запасом на "последний час"
SAMPLE_INTERVAL_SECONDS = 60


class RedisMetricsHistory(IMetricsHistory):
    def __init__(self, redis_url: str, key: str = "admin:metrics_history") -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        self._key = key
        self._last_ts_key = f"{key}:last_ts"

    async def record(self, cpu_percent: float, memory_percent: float) -> None:
        try:
            now = time.time()
            last_raw = await self._redis.get(self._last_ts_key)
            if last_raw is not None and now - float(last_raw) < SAMPLE_INTERVAL_SECONDS:
                return  # недавно уже записали точку — не захламляем список
            point = {"ts": int(now), "cpu_percent": cpu_percent, "memory_percent": memory_percent}
            await self._redis.lpush(self._key, json.dumps(point))
            await self._redis.ltrim(self._key, 0, _MAX_POINTS - 1)
            await self._redis.set(self._last_ts_key, now, ex=SAMPLE_INTERVAL_SECONDS * 2)
        except Exception:
            _logger.exception("Не удалось записать точку истории метрик (Redis)")

    async def list_recent(self) -> list[dict]:
        try:
            raw = await self._redis.lrange(self._key, 0, _MAX_POINTS - 1)
        except Exception:
            _logger.exception("Не удалось прочитать историю метрик (Redis)")
            return []
        points = []
        for item in raw:
            try:
                points.append(json.loads(item))
            except Exception:
                continue
        return list(reversed(points))  # старые сначала — так проще рисовать график


metrics_history: IMetricsHistory | None = None
if settings.cache_redis_url:
    metrics_history = RedisMetricsHistory(settings.cache_redis_url)
