from datetime import date

from pydantic import BaseModel, Field

from app.application.admin.get_server_status import MetricsPoint, RecentTenant, ServerStatusResult
from app.application.admin.get_tenant_detail import TenantDetail
from app.application.admin.list_tenants import TenantListItem
from app.application.admin.platform_banners import BannerFields
from app.application.admin.platform_categories import (
    CreatePlatformCategoryCommand,
    UpdatePlatformCategoryCommand,
)
from app.domain.platform.banners import PlatformBanner
from app.domain.platform.entities import PlatformCategory


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
    is_verified: bool
    created_at: str

    @classmethod
    def from_item(cls, item: TenantListItem) -> "TenantListItemResponse":
        return cls(
            id=item.id,
            name=item.name,
            slug=item.slug,
            storefront_enabled=item.storefront_enabled,
            is_suspended=item.is_suspended,
            is_verified=item.is_verified,
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
    is_verified: bool
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
            is_verified=d.is_verified,
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


class PlatformCategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    parent_id: int | None = None

    model_config = {"extra": "forbid"}

    def to_command(self) -> CreatePlatformCategoryCommand:
        return CreatePlatformCategoryCommand(
            name=self.name, slug=self.slug, sort_order=self.sort_order, parent_id=self.parent_id
        )


class PlatformCategoryUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    is_active: bool = True
    parent_id: int | None = None

    model_config = {"extra": "forbid"}

    def to_command(self, category_id: int) -> UpdatePlatformCategoryCommand:
        return UpdatePlatformCategoryCommand(
            category_id=category_id, name=self.name, slug=self.slug,
            sort_order=self.sort_order, is_active=self.is_active, parent_id=self.parent_id,
        )


class PlatformCategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    image: str
    sort_order: int
    is_active: bool
    parent_id: int | None

    @classmethod
    def from_entity(cls, category: PlatformCategory) -> "PlatformCategoryResponse":
        return cls(
            id=category.id,
            name=category.name,
            slug=category.slug,
            image=category.image,
            sort_order=category.sort_order,
            is_active=category.is_active,
            parent_id=category.parent_id,
        )


class BannerRequest(BaseModel):
    """Общее тело создания/редактирования баннера — is_active игнорируется при
    создании (новый баннер всегда активен), как и у PlatformCategory*Request."""

    placement: str
    title: str = Field(min_length=1, max_length=300)
    subtitle: str = Field("", max_length=500)
    button_text: str = Field("", max_length=100)
    link: str = Field("", max_length=500)
    theme: str = "light"
    sort_order: int = 0
    starts_at: date | None = None
    ends_at: date | None = None
    city: str | None = None
    is_active: bool = True

    model_config = {"extra": "forbid"}

    def to_fields(self) -> BannerFields:
        return BannerFields(
            placement=self.placement,
            title=self.title,
            subtitle=self.subtitle,
            button_text=self.button_text,
            link=self.link,
            theme=self.theme,
            sort_order=self.sort_order,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            city=self.city,
            is_active=self.is_active,
        )


class BannerResponse(BaseModel):
    id: int
    placement: str
    title: str
    subtitle: str
    button_text: str
    link: str
    image: str
    image_mobile: str
    theme: str
    sort_order: int
    is_active: bool
    starts_at: date | None
    ends_at: date | None
    city: str | None

    @classmethod
    def from_entity(cls, banner: PlatformBanner) -> "BannerResponse":
        return cls(
            id=banner.id,
            placement=banner.placement,
            title=banner.title,
            subtitle=banner.subtitle,
            button_text=banner.button_text,
            link=banner.link,
            image=banner.image,
            image_mobile=banner.image_mobile,
            theme=banner.theme,
            sort_order=banner.sort_order,
            is_active=banner.is_active,
            starts_at=banner.starts_at,
            ends_at=banner.ends_at,
            city=banner.city,
        )
