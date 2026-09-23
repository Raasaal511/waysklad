from dataclasses import dataclass

import psutil
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import text

from app.infrastructure.config import settings
from app.infrastructure.files import UPLOAD_DIR
from app.infrastructure.observability.status_files import read_backup_status, read_tls_status

APP_VERSION = "0.1.0"
from sqlalchemy import func, select

from app.domain.common.cache import ICache
from app.infrastructure.db.models.identity import TenantModel, UserModel
from app.infrastructure.observability.logging import get_logger
from app.infrastructure.observability.metrics_history import metrics_history

_logger = get_logger("app.admin")

# psutil.cpu_percent(interval=None) — неблокирующий, сравнивает с моментом
# предыдущего вызова (а не спит interval секунд в event loop). Первый вызов
# после старта процесса всегда вернёт 0.0 — это нормально, вызывающий код
# сюда обращается периодически (кешируется на STATUS_CACHE_TTL_SECONDS в
# роутере), поэтому реальные значения появляются со второго обращения.
psutil.cpu_percent(interval=None)


@dataclass(frozen=True)
class RecentTenant:
    id: int
    name: str
    slug: str | None
    created_at: str


@dataclass(frozen=True)
class MetricsPoint:
    ts: int
    cpu_percent: float
    memory_percent: float


@dataclass(frozen=True)
class AppInfo:
    version: str
    git_sha: str
    started_at: str | None
    uptime_seconds: int | None
    workers: int


@dataclass(frozen=True)
class DbInfo:
    """slowest_query_ms_1h требует pg_stat_statements; расширения нет — None,
    а не ноль: «не знаем» и «всё быстро» это разные вещи."""

    ok: bool
    size_bytes: int | None
    connections_active: int | None
    connections_max: int | None
    slowest_query_ms_1h: float | None


@dataclass(frozen=True)
class RedisInfo:
    ok: bool
    used_memory: int | None
    keys: int | None
    hit_rate_1h: float | None


@dataclass(frozen=True)
class UploadsInfo:
    files_count: int
    size_bytes: int


@dataclass(frozen=True)
class ApiInfo:
    rps_1h: float | None
    p50_ms: int | None
    p95_ms: int | None
    errors_5xx_24h: int
    errors_4xx_24h: int


@dataclass(frozen=True)
class ServerStatusResult:
    db_connected: bool
    redis_connected: bool
    active_users: int
    active_tenants: int
    online_now: int  # WebSocket-соединения ТОЛЬКО этого воркера, не всей платформы
    cpu_percent: float
    memory_percent: float
    memory_used_mb: int
    memory_total_mb: int
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    recent_tenants: list[RecentTenant]
    history: list[MetricsPoint]
    load_avg: list[float] | None = None
    disk_free_percent: float | None = None
    app: AppInfo | None = None
    db: DbInfo | None = None
    redis: RedisInfo | None = None
    uploads: UploadsInfo | None = None
    api: ApiInfo | None = None
    backup: dict | None = None
    tls: dict | None = None


async def get_server_status(
    session_factory,
    cache: ICache,
    online_now: int,
    api_metrics=None,
    started_at: datetime | None = None,
) -> ServerStatusResult:
    """Platform-wide метрики — прямой запрос без tenant-скоупинга (как
    uow.tenants.list_all()), поэтому не через обычный per-tenant UnitOfWork."""
    db_connected = True
    active_users = 0
    active_tenants = 0
    try:
        async with session_factory() as session:
            active_users = (
                await session.execute(
                    select(func.count()).select_from(UserModel).where(UserModel.is_active.is_(True))
                )
            ).scalar_one()
            active_tenants = (
                await session.execute(select(func.count()).select_from(TenantModel))
            ).scalar_one()
    except Exception:
        _logger.exception("Не удалось получить статус БД для admin-эндпоинта")
        db_connected = False

    redis_connected = await _check_redis(cache)

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    recent_tenants: list[RecentTenant] = []
    try:
        async with session_factory() as session:
            rows = (
                await session.execute(
                    select(TenantModel.id, TenantModel.name, TenantModel.slug, TenantModel.created_at)
                    .order_by(TenantModel.created_at.desc())
                    .limit(5)
                )
            ).all()
            recent_tenants = [
                RecentTenant(id=r.id, name=r.name, slug=r.slug, created_at=r.created_at.isoformat())
                for r in rows
            ]
    except Exception:
        _logger.exception("Не удалось получить недавние магазины для admin-эндпоинта")

    cpu_percent = psutil.cpu_percent(interval=None)

    history: list[MetricsPoint] = []
    if metrics_history is not None:
        await metrics_history.record(cpu_percent, memory.percent)
        history = [
            MetricsPoint(ts=p["ts"], cpu_percent=p["cpu_percent"], memory_percent=p["memory_percent"])
            for p in await metrics_history.list_recent()
        ]

    return ServerStatusResult(
        db_connected=db_connected,
        redis_connected=redis_connected,
        active_users=active_users,
        active_tenants=active_tenants,
        online_now=online_now,
        cpu_percent=cpu_percent,
        memory_percent=memory.percent,
        memory_used_mb=(memory.total - memory.available) // (1024 * 1024),
        memory_total_mb=memory.total // (1024 * 1024),
        disk_percent=disk.percent,
        disk_used_gb=round(disk.used / (1024**3), 1),
        disk_total_gb=round(disk.total / (1024**3), 1),
        recent_tenants=recent_tenants,
        history=history,
        load_avg=_load_avg(),
        disk_free_percent=round(100 - disk.percent, 1),
        app=_app_info(started_at),
        db=await _db_info(session_factory, db_connected),
        redis=await _redis_info(cache, redis_connected),
        uploads=_uploads_info(),
        api=await _api_info(api_metrics),
        backup=_backup_json(),
        tls=_tls_json(),
    )


def _load_avg() -> list[float] | None:
    try:
        return [round(v, 2) for v in psutil.getloadavg()]
    except (AttributeError, OSError):
        # getloadavg есть не везде (Windows) — лучше None, чем выдуманные нули
        return None


def _app_info(started_at: datetime | None) -> AppInfo:
    uptime = (
        int((datetime.now(timezone.utc) - started_at).total_seconds())
        if started_at
        else None
    )
    return AppInfo(
        version=APP_VERSION,
        git_sha=settings.git_sha,
        started_at=started_at.isoformat() if started_at else None,
        uptime_seconds=uptime,
        workers=_worker_count(),
    )


def _worker_count() -> int:
    """Сколько uvicorn-воркеров поднято. Считаем процессы с тем же именем, что
    и текущий: --workers N порождает дочерние процессы одного образа."""
    try:
        current = psutil.Process()
        parent = current.parent()
        if parent is None:
            return 1
        siblings = [c for c in parent.children() if c.name() == current.name()]
        return max(len(siblings), 1)
    except Exception:  # noqa: BLE001 — метрика, а не бизнес-логика
        return 1


async def _db_info(session_factory, ok: bool) -> DbInfo:
    if not ok:
        return DbInfo(
            ok=False,
            size_bytes=None,
            connections_active=None,
            connections_max=None,
            slowest_query_ms_1h=None,
        )
    size = connections = max_connections = None
    slowest = None
    try:
        async with session_factory() as session:
            size = (
                await session.execute(text("SELECT pg_database_size(current_database())"))
            ).scalar_one()
            connections = (
                await session.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                )
            ).scalar_one()
            max_connections = int(
                (await session.execute(text("SHOW max_connections"))).scalar_one()
            )
            # pg_stat_statements ставится не везде — без него честно отдаём None
            try:
                slowest = (
                    await session.execute(
                        text("SELECT max(max_exec_time) FROM pg_stat_statements")
                    )
                ).scalar_one()
            except Exception:  # noqa: BLE001
                slowest = None
    except Exception:  # noqa: BLE001
        _logger.exception("Не удалось получить метрики БД для admin-эндпоинта")

    return DbInfo(
        ok=ok,
        size_bytes=int(size) if size is not None else None,
        connections_active=int(connections) if connections is not None else None,
        connections_max=max_connections,
        slowest_query_ms_1h=round(float(slowest), 2) if slowest is not None else None,
    )


async def _redis_info(cache: ICache, ok: bool) -> RedisInfo:
    if not ok or not hasattr(cache, "raw"):
        return RedisInfo(ok=ok, used_memory=None, keys=None, hit_rate_1h=None)
    try:
        info = await cache.raw.info()
        keys = await cache.raw.dbsize()
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        # hit rate с момента старта Redis, не строго за час: точной почасовой
        # разбивки Redis не ведёт, а заводить свой счётчик ради неё избыточно
        hit_rate = round(hits / total, 3) if total else None
        return RedisInfo(
            ok=True,
            used_memory=int(info.get("used_memory", 0)),
            keys=int(keys),
            hit_rate_1h=hit_rate,
        )
    except Exception:  # noqa: BLE001
        _logger.exception("Не удалось получить метрики Redis для admin-эндпоинта")
        return RedisInfo(ok=ok, used_memory=None, keys=None, hit_rate_1h=None)


def _uploads_info() -> UploadsInfo:
    count = 0
    size = 0
    try:
        for path in UPLOAD_DIR.rglob("*"):
            if path.is_file():
                count += 1
                size += path.stat().st_size
    except OSError:
        _logger.warning("Не удалось посчитать uploads", exc_info=True)
    return UploadsInfo(files_count=count, size_bytes=size)


async def _api_info(collector) -> ApiInfo:
    if collector is None:
        return ApiInfo(
            rps_1h=None, p50_ms=None, p95_ms=None, errors_5xx_24h=0, errors_4xx_24h=0
        )
    try:
        metrics = await collector.read()
    except Exception:  # noqa: BLE001
        _logger.exception("Не удалось прочитать метрики API")
        return ApiInfo(
            rps_1h=None, p50_ms=None, p95_ms=None, errors_5xx_24h=0, errors_4xx_24h=0
        )
    return ApiInfo(
        rps_1h=metrics.rps_1h,
        p50_ms=metrics.p50_ms,
        p95_ms=metrics.p95_ms,
        errors_5xx_24h=metrics.errors_5xx_24h,
        errors_4xx_24h=metrics.errors_4xx_24h,
    )


def _backup_json() -> dict | None:
    status = read_backup_status()
    return asdict(status) if status else None


def _tls_json() -> dict | None:
    status = read_tls_status()
    return asdict(status) if status else None


async def _check_redis(cache: ICache) -> bool:
    # RedisCache.get/set сами глотают исключения на сбое соединения (см.
    # app.infrastructure.cache.redis_cache) — недоступность видна по несовпадению значения,
    # не по exception
    probe_key = "admin:redis_probe"
    await cache.set(probe_key, b"1", ttl_seconds=5)
    return await cache.get(probe_key) == b"1"
