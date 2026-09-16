from dataclasses import dataclass

import psutil
from sqlalchemy import func, select

from app.domain.common.cache import ICache
from app.infrastructure.db.models.identity import TenantModel, UserModel
from app.infrastructure.observability.logging import get_logger

_logger = get_logger("app.admin")

# psutil.cpu_percent(interval=None) — неблокирующий, сравнивает с моментом
# предыдущего вызова (а не спит interval секунд в event loop). Первый вызов
# после старта процесса всегда вернёт 0.0 — это нормально, вызывающий код
# сюда обращается периодически (кешируется на STATUS_CACHE_TTL_SECONDS в
# роутере), поэтому реальные значения появляются со второго обращения.
psutil.cpu_percent(interval=None)


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


async def get_server_status(session_factory, cache: ICache, online_now: int) -> ServerStatusResult:
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

    return ServerStatusResult(
        db_connected=db_connected,
        redis_connected=redis_connected,
        active_users=active_users,
        active_tenants=active_tenants,
        online_now=online_now,
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_percent=memory.percent,
        memory_used_mb=(memory.total - memory.available) // (1024 * 1024),
        memory_total_mb=memory.total // (1024 * 1024),
    )


async def _check_redis(cache: ICache) -> bool:
    # RedisCache.get/set сами глотают исключения на сбое соединения (см.
    # app.infrastructure.cache.redis_cache) — недоступность видна по несовпадению значения,
    # не по exception
    probe_key = "admin:redis_probe"
    await cache.set(probe_key, b"1", ttl_seconds=5)
    return await cache.get(probe_key) == b"1"
