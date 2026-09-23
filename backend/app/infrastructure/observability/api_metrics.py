"""Счётчик запросов API: RPS, p50/p95, ошибки за сутки.

Своими силами, без Grafana и Sentry — задача прямо просит не тащить внешние
системы. Данные живут в Redis, поэтому счётчик общий для всех uvicorn-воркеров:
в проде их несколько, и счётчик в памяти процесса показывал бы N-ю долю правды.

Устройство: на каждую минуту заводится своя запись, минуты старше окна
истекают сами по TTL. Длительности хранятся не поштучно, а в виде гистограммы
по фиксированным корзинам — так запись занимает десятки байт независимо от
нагрузки, а p50/p95 считаются по накопленным частотам. Точность перцентиля
ограничена шириной корзины, и это честный размен: считать точные перцентили
по каждому запросу дороже, чем стоит сама метрика.
"""

import time
from dataclasses import dataclass

from redis.asyncio import Redis

# границы корзин в миллисекундах; последняя корзина — «дольше 5 секунд»
BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
WINDOW_MINUTES = 60
ERROR_WINDOW_HOURS = 24
# минутные ключи нужны только для часового окна перцентилей, часовые — для
# суточного счётчика ошибок; обе группы истекают сами, чистить их не нужно
_MINUTE_TTL_SECONDS = (WINDOW_MINUTES + 5) * 60
_HOUR_TTL_SECONDS = (ERROR_WINDOW_HOURS + 1) * 3600

_PREFIX = "api_metrics"


def _minute_key(minute: int) -> str:
    return f"{_PREFIX}:m:{minute}"


def _hour_key(hour: int) -> str:
    return f"{_PREFIX}:h:{hour}"


def _decode(entry: dict) -> dict[str, int]:
    return {
        (k.decode() if isinstance(k, bytes) else k): int(v) for k, v in entry.items()
    }


def _bucket_for(duration_ms: float) -> str:
    for edge in BUCKETS_MS:
        if duration_ms <= edge:
            return str(edge)
    return "inf"


@dataclass(frozen=True)
class ApiMetrics:
    """None там, где данных ещё нет: за окно не было ни одного запроса.
    Ноль означал бы «запросов не было и всё быстро», а это разные вещи."""

    rps_1h: float | None
    p50_ms: int | None
    p95_ms: int | None
    errors_5xx_24h: int
    errors_4xx_24h: int


class ApiMetricsCollector:
    def __init__(self, redis: Redis):
        self._redis = redis

    async def record(self, duration_ms: float, status_code: int) -> None:
        minute = int(time.time()) // 60
        key = _minute_key(minute)
        pipe = self._redis.pipeline()
        pipe.hincrby(key, "count", 1)
        pipe.hincrby(key, f"b:{_bucket_for(duration_ms)}", 1)
        pipe.expire(key, _MINUTE_TTL_SECONDS)

        # ошибки считаются ещё и по часам: суточное окно из минутных ключей
        # стоило бы 1440 обращений к Redis на каждое чтение /status
        if 400 <= status_code < 600:
            hour_key = _hour_key(minute // 60)
            field = "e5xx" if status_code >= 500 else "e4xx"
            pipe.hincrby(hour_key, field, 1)
            pipe.expire(hour_key, _HOUR_TTL_SECONDS)
        await pipe.execute()

    async def read(self) -> ApiMetrics:
        now = int(time.time())
        now_minute = now // 60
        now_hour = now // 3600

        pipe = self._redis.pipeline()
        for i in range(WINDOW_MINUTES):
            pipe.hgetall(_minute_key(now_minute - i))
        for i in range(ERROR_WINDOW_HOURS):
            pipe.hgetall(_hour_key(now_hour - i))
        raw = await pipe.execute()

        hour_total = 0
        histogram: dict[str, int] = {}
        errors_5xx = 0
        errors_4xx = 0

        for entry in raw[:WINDOW_MINUTES]:
            if not entry:
                continue
            decoded = _decode(entry)
            hour_total += decoded.get("count", 0)
            for name, value in decoded.items():
                if name.startswith("b:"):
                    histogram[name[2:]] = histogram.get(name[2:], 0) + value

        for entry in raw[WINDOW_MINUTES:]:
            if not entry:
                continue
            decoded = _decode(entry)
            errors_5xx += decoded.get("e5xx", 0)
            errors_4xx += decoded.get("e4xx", 0)

        if hour_total == 0:
            return ApiMetrics(
                rps_1h=None,
                p50_ms=None,
                p95_ms=None,
                errors_5xx_24h=errors_5xx,
                errors_4xx_24h=errors_4xx,
            )

        return ApiMetrics(
            rps_1h=round(hour_total / (WINDOW_MINUTES * 60), 3),
            p50_ms=_percentile(histogram, hour_total, 0.50),
            p95_ms=_percentile(histogram, hour_total, 0.95),
            errors_5xx_24h=errors_5xx,
            errors_4xx_24h=errors_4xx,
        )


def _percentile(histogram: dict[str, int], total: int, share: float) -> int | None:
    """Верхняя граница корзины, в которую попадает нужная доля запросов.

    Значение округлено вверх до границы корзины — «p95 не хуже этого».
    """
    if total == 0:
        return None
    target = total * share
    seen = 0
    for edge in BUCKETS_MS:
        seen += histogram.get(str(edge), 0)
        if seen >= target:
            return edge
    # перцентиль попал в корзину «дольше последней границы»: точнее сказать
    # нечем, отдаём саму границу — значение читается как «не меньше этого»
    return BUCKETS_MS[-1]



async def metrics_middleware(request, call_next):
    """Замеряет длительность и статус каждого запроса к API.

    Сбор метрик не должен ронять запрос: любая ошибка Redis глотается — без
    метрик жить можно, без ответа пользователю нельзя. Статика и сам /status
    не считаются, иначе админка накручивала бы себе RPS.
    """
    collector = getattr(request.app.state, "api_metrics", None)
    path = request.url.path
    if collector is None or not path.startswith("/api/") or path.endswith("/status"):
        return await call_next(request)

    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    try:
        await collector.record(duration_ms, response.status_code)
    except Exception:  # noqa: BLE001 — метрики не важнее ответа
        pass
    return response
