import dataclasses
from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.application.admin.get_server_status import ServerStatusResult, get_server_status
from app.infrastructure.cache_aside import cached
from app.infrastructure.ws_broadcast import broadcaster
from app.presentation.admin.schemas import ErrorLogResponse, ServerStatusResponse
from app.presentation.deps.admin import ErrorLogDep, require_admin_token
from app.presentation.deps.cache import CacheDep
from app.presentation.deps.session import SessionFactoryDep

_STATUS_CACHE_TTL_SECONDS = 5

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_token)]
)


@router.get("/status")
async def admin_status(factory: SessionFactoryDep, cache: CacheDep) -> ServerStatusResponse:
    # online_now — мгновенный и бесплатный (len() по памяти этого воркера),
    # не кешируем вместе с db_connected/active_users (те требуют SQL-запроса)
    cached_result = await cached(
        cache,
        "admin:status",
        _STATUS_CACHE_TTL_SECONDS,
        lambda: get_server_status(factory, cache, online_now=0),
        to_json=lambda r: asdict(r),
        from_json=lambda d: ServerStatusResult(**d),
    )
    result = dataclasses.replace(
        cached_result, online_now=broadcaster.registry.count_connections()
    )
    return ServerStatusResponse.from_result(result)


@router.get("/error-logs")
async def admin_error_logs(error_log: ErrorLogDep, limit: int = 50) -> ErrorLogResponse:
    if error_log is None:
        return ErrorLogResponse(errors=[])
    limit = min(limit, 200)
    entries = await error_log.list_recent(limit)
    return ErrorLogResponse(errors=entries)
