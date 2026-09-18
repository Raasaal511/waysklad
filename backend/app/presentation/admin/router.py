import dataclasses
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from app.application.admin.get_server_status import (
    MetricsPoint,
    RecentTenant,
    ServerStatusResult,
    get_server_status,
)
from app.application.admin.get_tenant_detail import get_tenant_detail
from app.application.admin.list_tenants import list_tenants
from app.application.admin.platform_categories import (
    create_platform_category,
    delete_platform_category,
    list_all_platform_categories,
    set_platform_category_image,
    update_platform_category,
)
from app.application.admin.set_tenant_suspended import set_tenant_suspended
from app.application.admin.set_tenant_verified import set_tenant_verified
from app.domain.common.exceptions import NotFoundError
from app.infrastructure.cache.cache_aside import cached
from app.infrastructure.config import settings
from app.infrastructure.rate_limit import limiter
from app.infrastructure.security import create_admin_access_token, verify_password
from app.infrastructure.notifications.ws_broadcast import broadcaster
from app.presentation.admin.schemas import (
    AdminLoginRequest,
    AdminTokenResponse,
    ErrorLogResponse,
    PlatformCategoryCreateRequest,
    PlatformCategoryResponse,
    PlatformCategoryUpdateRequest,
    ServerStatusResponse,
    TenantDetailResponse,
    TenantListItemResponse,
    TenantListResponse,
)
from app.presentation.deps.admin import ErrorLogDep, require_admin_token
from app.presentation.deps.cache import CacheDep
from app.presentation.deps.security import FileStorageDep
from app.presentation.deps.session import SessionFactoryDep

_STATUS_CACHE_TTL_SECONDS = 5

# без dependencies=[require_admin_token] — сюда заходят без токена, чтобы его получить
public_router = APIRouter(prefix="/admin", tags=["admin"])

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_token)]
)


@public_router.post("/login")
@limiter.limit("10/hour")
async def admin_login(request: Request, body: AdminLoginRequest) -> AdminTokenResponse:
    valid = bool(settings.admin_login) and bool(settings.admin_password_hash)
    # сравнение логина тоже через verify_password (bcrypt) — не secrets.compare_digest
    # по строке, чтобы не давать даже теоретическую временную утечку через login
    if not valid or body.login != settings.admin_login:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    if not verify_password(body.password, settings.admin_password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return AdminTokenResponse(
        access_token=create_admin_access_token(),
        expires_in_minutes=settings.admin_token_expire_minutes,
    )


@router.get("/status")
async def admin_status(factory: SessionFactoryDep, cache: CacheDep) -> ServerStatusResponse:
    # online_now — сумма по всем --workers N через общий Redis-счётчик (см.
    # Broadcaster.online_now), не кешируем вместе с db_connected/active_users
    # (те требуют SQL-запроса, online_now должен быть мгновенным)
    def _from_json(d: dict) -> ServerStatusResult:
        d = dict(d)
        d["recent_tenants"] = [RecentTenant(**t) for t in d["recent_tenants"]]
        d["history"] = [MetricsPoint(**p) for p in d["history"]]
        return ServerStatusResult(**d)

    cached_result = await cached(
        cache,
        "admin:status",
        _STATUS_CACHE_TTL_SECONDS,
        lambda: get_server_status(factory, cache, online_now=0),
        to_json=lambda r: asdict(r),
        from_json=_from_json,
    )
    result = dataclasses.replace(
        cached_result, online_now=await broadcaster.online_now()
    )
    return ServerStatusResponse.from_result(result)


@router.get("/error-logs")
async def admin_error_logs(error_log: ErrorLogDep, limit: int = 50) -> ErrorLogResponse:
    if error_log is None:
        return ErrorLogResponse(errors=[])
    limit = min(limit, 200)
    entries = await error_log.list_recent(limit)
    return ErrorLogResponse(errors=entries)


@router.get("/tenants")
async def admin_list_tenants(factory: SessionFactoryDep) -> TenantListResponse:
    items = await list_tenants(factory)
    return TenantListResponse(tenants=[TenantListItemResponse.from_item(i) for i in items])


@router.get("/tenants/{tenant_id}")
async def admin_get_tenant(tenant_id: int, factory: SessionFactoryDep) -> TenantDetailResponse:
    detail = await get_tenant_detail(factory, tenant_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    return TenantDetailResponse.from_detail(detail)


@router.post("/tenants/{tenant_id}/suspend")
async def admin_suspend_tenant(
    tenant_id: int, factory: SessionFactoryDep, cache: CacheDep
) -> TenantDetailResponse:
    applied = await set_tenant_suspended(factory, cache, tenant_id, suspended=True)
    if not applied:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    detail = await get_tenant_detail(factory, tenant_id)
    return TenantDetailResponse.from_detail(detail)


@router.post("/tenants/{tenant_id}/unsuspend")
async def admin_unsuspend_tenant(
    tenant_id: int, factory: SessionFactoryDep, cache: CacheDep
) -> TenantDetailResponse:
    applied = await set_tenant_suspended(factory, cache, tenant_id, suspended=False)
    if not applied:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    detail = await get_tenant_detail(factory, tenant_id)
    return TenantDetailResponse.from_detail(detail)


@router.post("/tenants/{tenant_id}/verify")
async def admin_verify_tenant(
    tenant_id: int, factory: SessionFactoryDep, cache: CacheDep
) -> TenantDetailResponse:
    applied = await set_tenant_verified(factory, cache, tenant_id, verified=True)
    if not applied:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    detail = await get_tenant_detail(factory, tenant_id)
    return TenantDetailResponse.from_detail(detail)


@router.post("/tenants/{tenant_id}/unverify")
async def admin_unverify_tenant(
    tenant_id: int, factory: SessionFactoryDep, cache: CacheDep
) -> TenantDetailResponse:
    applied = await set_tenant_verified(factory, cache, tenant_id, verified=False)
    if not applied:
        raise HTTPException(status_code=404, detail="Магазин не найден")
    detail = await get_tenant_detail(factory, tenant_id)
    return TenantDetailResponse.from_detail(detail)


@router.get("/platform-categories")
async def admin_list_platform_categories(
    factory: SessionFactoryDep,
) -> list[PlatformCategoryResponse]:
    categories = await list_all_platform_categories(factory)
    return [PlatformCategoryResponse.from_entity(c) for c in categories]


@router.post("/platform-categories", status_code=201)
async def admin_create_platform_category(
    body: PlatformCategoryCreateRequest, factory: SessionFactoryDep
) -> PlatformCategoryResponse:
    category = await create_platform_category(factory, body.to_command())
    return PlatformCategoryResponse.from_entity(category)


@router.put("/platform-categories/{category_id}")
async def admin_update_platform_category(
    category_id: int, body: PlatformCategoryUpdateRequest, factory: SessionFactoryDep
) -> PlatformCategoryResponse:
    category = await update_platform_category(factory, body.to_command(category_id))
    if category is None:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return PlatformCategoryResponse.from_entity(category)


@router.delete("/platform-categories/{category_id}")
async def admin_delete_platform_category(
    category_id: int, factory: SessionFactoryDep
) -> PlatformCategoryResponse:
    category = await delete_platform_category(factory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return PlatformCategoryResponse.from_entity(category)


@router.post("/platform-categories/{category_id}/image", status_code=201)
async def admin_set_platform_category_image(
    category_id: int, file: UploadFile, factory: SessionFactoryDep, storage: FileStorageDep
) -> PlatformCategoryResponse:
    try:
        category = await set_platform_category_image(
            factory, storage, category_id, file.filename or "category.jpg", await file.read()
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return PlatformCategoryResponse.from_entity(category)
