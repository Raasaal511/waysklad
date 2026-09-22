import dataclasses
from dataclasses import asdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from app.application.admin.get_overview import (
    CACHE_TTL_SECONDS as OVERVIEW_CACHE_TTL_SECONDS,
)
from app.application.admin.get_overview import PlatformOverview, get_platform_overview
from app.application.admin.get_server_status import (
    MetricsPoint,
    RecentTenant,
    ServerStatusResult,
    get_server_status,
)
from app.application.admin.get_tenant_detail import get_tenant_detail
from app.application.admin.list_tenants import (
    CACHE_TTL_SECONDS as TENANTS_CACHE_TTL_SECONDS,
)
from app.application.admin.list_tenants import (
    DEFAULT_LIMIT as TENANTS_DEFAULT_LIMIT,
)
from app.application.admin.list_tenants import (
    TenantListItem,
    TenantListResult,
    list_tenants,
)
from app.application.admin.platform_banners import (
    create_platform_banner,
    delete_platform_banner,
    list_all_platform_banners,
    set_platform_banner_image,
    update_platform_banner,
)
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
    PlatformOverviewResponse,
    AdminLoginRequest,
    AdminTokenResponse,
    BannerRequest,
    BannerResponse,
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
async def admin_status(
    request: Request, factory: SessionFactoryDep, cache: CacheDep
) -> ServerStatusResponse:
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
        lambda: get_server_status(
            factory,
            cache,
            online_now=0,
            api_metrics=getattr(request.app.state, "api_metrics", None),
            started_at=getattr(request.app.state, "started_at", None),
        ),
        to_json=lambda r: asdict(r),
        from_json=_from_json,
    )
    result = dataclasses.replace(
        cached_result, online_now=await broadcaster.online_now()
    )
    return ServerStatusResponse.from_result(result)


@router.get("/overview")
async def admin_overview(factory: SessionFactoryDep, cache: CacheDep) -> PlatformOverviewResponse:
    """Сводка по платформе. Кросс-тенантные агрегаты считаются в SQL —
    см. application/admin/get_overview.py."""
    result = await cached(
        cache,
        "admin:overview",
        OVERVIEW_CACHE_TTL_SECONDS,
        lambda: get_platform_overview(factory),
        to_json=lambda r: r.to_json(),
        from_json=PlatformOverview.from_json,
    )
    return PlatformOverviewResponse.from_result(result)


@router.get("/error-logs")
async def admin_error_logs(error_log: ErrorLogDep, limit: int = 50) -> ErrorLogResponse:
    if error_log is None:
        return ErrorLogResponse(errors=[])
    limit = min(limit, 200)
    entries = await error_log.list_recent(limit)
    return ErrorLogResponse(errors=entries)


@router.get("/tenants")
async def admin_list_tenants(
    factory: SessionFactoryDep,
    cache: CacheDep,
    query: str = "",
    status: str = "all",
    storefront: str | None = None,
    sort: str = "last_activity",
    limit: int = TENANTS_DEFAULT_LIMIT,
    offset: int = 0,
) -> TenantListResponse:
    """Агрегаты по всем магазинам — кросс-тенантные запросы, см.
    application/admin/list_tenants.py. Кеш общий на набор параметров."""
    key = f"admin:tenants:{query}:{status}:{storefront}:{sort}:{limit}:{offset}"
    result = await cached(
        cache,
        key,
        TENANTS_CACHE_TTL_SECONDS,
        lambda: list_tenants(
            factory,
            query=query,
            status=status,
            storefront=storefront,
            sort=sort,
            limit=min(max(limit, 1), 200),
            offset=max(offset, 0),
        ),
        to_json=lambda r: {
            "items": [_tenant_item_json(i) for i in r.items],
            "total": r.total,
            "counts_by_health": r.counts_by_health,
        },
        from_json=lambda d: TenantListResult(
            items=[TenantListItem(**_tenant_item_from_json(i)) for i in d["items"]],
            total=d["total"],
            counts_by_health=d["counts_by_health"],
        ),
    )
    return TenantListResponse(
        tenants=[TenantListItemResponse.from_item(i) for i in result.items],
        total=result.total,
        counts_by_health=result.counts_by_health,
    )


def _tenant_item_json(item: TenantListItem) -> dict:
    d = asdict(item)
    d["sales_sum_30d"] = str(d["sales_sum_30d"])  # Decimal не сериализуется в JSON
    return d


def _tenant_item_from_json(d: dict) -> dict:
    d = dict(d)
    d["sales_sum_30d"] = Decimal(d["sales_sum_30d"])
    return d


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


@router.get("/banners")
async def admin_list_banners(factory: SessionFactoryDep) -> list[BannerResponse]:
    banners = await list_all_platform_banners(factory)
    return [BannerResponse.from_entity(b) for b in banners]


@router.post("/banners", status_code=201)
async def admin_create_banner(
    body: BannerRequest, factory: SessionFactoryDep, cache: CacheDep
) -> BannerResponse:
    banner = await create_platform_banner(factory, cache, body.to_fields())
    return BannerResponse.from_entity(banner)


@router.put("/banners/{banner_id}")
async def admin_update_banner(
    banner_id: int, body: BannerRequest, factory: SessionFactoryDep, cache: CacheDep
) -> BannerResponse:
    banner = await update_platform_banner(factory, cache, banner_id, body.to_fields())
    if banner is None:
        raise HTTPException(status_code=404, detail="Баннер не найден")
    return BannerResponse.from_entity(banner)


@router.delete("/banners/{banner_id}")
async def admin_delete_banner(
    banner_id: int, factory: SessionFactoryDep, cache: CacheDep, storage: FileStorageDep
) -> BannerResponse:
    banner = await delete_platform_banner(factory, cache, storage, banner_id)
    if banner is None:
        raise HTTPException(status_code=404, detail="Баннер не найден")
    return BannerResponse.from_entity(banner)


@router.post("/banners/{banner_id}/image", status_code=201)
async def admin_set_banner_image(
    banner_id: int, file: UploadFile, factory: SessionFactoryDep, cache: CacheDep, storage: FileStorageDep
) -> BannerResponse:
    try:
        banner = await set_platform_banner_image(
            factory, cache, storage, banner_id, file.filename or "banner.jpg", await file.read()
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Баннер не найден")
    return BannerResponse.from_entity(banner)


@router.post("/banners/{banner_id}/image-mobile", status_code=201)
async def admin_set_banner_image_mobile(
    banner_id: int, file: UploadFile, factory: SessionFactoryDep, cache: CacheDep, storage: FileStorageDep
) -> BannerResponse:
    try:
        banner = await set_platform_banner_image(
            factory, cache, storage, banner_id, file.filename or "banner.jpg", await file.read(),
            mobile=True,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Баннер не найден")
    return BannerResponse.from_entity(banner)
