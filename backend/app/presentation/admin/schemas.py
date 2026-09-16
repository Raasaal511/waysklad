from pydantic import BaseModel

from app.application.admin.get_server_status import MetricsPoint, RecentTenant, ServerStatusResult
from app.application.admin.get_tenant_detail import TenantDetail
from app.application.admin.list_tenants import TenantListItem


class AdminLoginRequest(BaseModel):
    login: str
    password: str

    model_config = {"extra": "forbid"}


class AdminTokenResponse(BaseModel):
    access_token: str
    expires_in_minutes: int


class TenantListItemResponse(BaseModel):
    id: int
    name: str
    slug: str | None
    storefront_enabled: bool
    is_suspended: bool
    created_at: str

    @classmethod
    def from_item(cls, item: TenantListItem) -> "TenantListItemResponse":
        return cls(
            id=item.id,
            name=item.name,
            slug=item.slug,
            storefront_enabled=item.storefront_enabled,
            is_suspended=item.is_suspended,
            created_at=item.created_at,
        )


class TenantListResponse(BaseModel):
    tenants: list[TenantListItemResponse]


class TenantOwnerResponse(BaseModel):
    name: str
    phone: str


class TenantDetailResponse(BaseModel):
    id: int
    name: str
    slug: str | None
    storefront_enabled: bool
    is_suspended: bool
    created_at: str
    owner: TenantOwnerResponse | None
    users_count: int
    products_count: int
    warehouses_count: int
    last_sale_at: str | None

    @classmethod
    def from_detail(cls, d: TenantDetail) -> "TenantDetailResponse":
        return cls(
            id=d.id,
            name=d.name,
            slug=d.slug,
            storefront_enabled=d.storefront_enabled,
            is_suspended=d.is_suspended,
            created_at=d.created_at,
            owner=TenantOwnerResponse(name=d.owner.name, phone=d.owner.phone) if d.owner else None,
            users_count=d.users_count,
            products_count=d.products_count,
            warehouses_count=d.warehouses_count,
            last_sale_at=d.last_sale_at,
        )


class RecentTenantResponse(BaseModel):
    id: int
    name: str
    slug: str | None
    created_at: str

    @classmethod
    def from_entity(cls, tenant: RecentTenant) -> "RecentTenantResponse":
        return cls(id=tenant.id, name=tenant.name, slug=tenant.slug, created_at=tenant.created_at)


class MetricsPointResponse(BaseModel):
    ts: int
    cpu_percent: float
    memory_percent: float

    @classmethod
    def from_entity(cls, point: MetricsPoint) -> "MetricsPointResponse":
        return cls(ts=point.ts, cpu_percent=point.cpu_percent, memory_percent=point.memory_percent)


class ServerStatusResponse(BaseModel):
    db_connected: bool
    redis_connected: bool
    active_users: int
    active_tenants: int
    online_now: int
    # с NOTIFICATIONS_REDIS_URL (прод, --workers N) — сумма по всем воркерам
    # через общий счётчик; без него (dev, один процесс) — фактически то же
    # самое, но формально видит только текущий процесс
    online_now_note: str = "сумма по всем воркерам платформы"
    cpu_percent: float
    memory_percent: float
    memory_used_mb: int
    memory_total_mb: int
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    recent_tenants: list[RecentTenantResponse]
    history: list[MetricsPointResponse]

    @classmethod
    def from_result(cls, result: ServerStatusResult) -> "ServerStatusResponse":
        return cls(
            db_connected=result.db_connected,
            redis_connected=result.redis_connected,
            active_users=result.active_users,
            active_tenants=result.active_tenants,
            online_now=result.online_now,
            cpu_percent=result.cpu_percent,
            memory_percent=result.memory_percent,
            memory_used_mb=result.memory_used_mb,
            memory_total_mb=result.memory_total_mb,
            disk_percent=result.disk_percent,
            disk_used_gb=result.disk_used_gb,
            disk_total_gb=result.disk_total_gb,
            recent_tenants=[RecentTenantResponse.from_entity(t) for t in result.recent_tenants],
            history=[MetricsPointResponse.from_entity(p) for p in result.history],
        )


class ErrorLogEntryResponse(BaseModel):
    timestamp: str
    method: str
    path: str
    error_type: str
    message: str


class ErrorLogResponse(BaseModel):
    errors: list[ErrorLogEntryResponse]
