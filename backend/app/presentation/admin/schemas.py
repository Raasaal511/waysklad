from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.admin.get_overview import PlatformOverview
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
    """Строка списка магазинов. Только счётчики, даты и статусы — содержимого
    чужого бизнеса (суммы долгов по клиентам, закупочные цены) здесь нет."""

    id: int
    name: str
    slug: str | None
    city: str | None
    created_at: str
    is_suspended: bool
    is_verified: bool
    storefront_enabled: bool
    owner_name: str
    users_count: int
    warehouses_count: int
    products_count: int
    last_sale_at: str | None
    last_login_at: str | None
    sales_7d: int
    sales_30d: int
    sales_sum_30d: Decimal
    debts_open_count: int
    storefront_requests_30d: int
    health: str

    @classmethod
    def from_item(cls, item: TenantListItem) -> "TenantListItemResponse":
        return cls(**asdict(item))


class TenantListResponse(BaseModel):
    tenants: list[TenantListItemResponse]
    total: int = 0
    # счётчики для чипов фильтра — по всей платформе, а не по странице
    counts_by_health: dict[str, int] = {}


class TenantOwnerResponse(BaseModel):
    name: str
    phone: str


class TenantUserResponse(BaseModel):
    """Без телефона: это персональные данные сотрудника магазина."""

    id: int
    name: str
    role: str
    is_active: bool
    last_login_at: str | None


class TenantWarehouseResponse(BaseModel):
    id: int
    name: str
    address: str
    show_on_storefront: bool
    positions_count: int


class TenantTopProductResponse(BaseModel):
    id: int
    name: str
    sold_30d: str


class TenantStorefrontResponse(BaseModel):
    enabled: bool
    slug: str | None
    products_on_storefront: int
    requests_30d: int
    reviews_count: int


class TenantActivityResponse(BaseModel):
    """Без details: там бывают суммы и имена клиентов магазина."""

    at: str
    actor_name: str
    action: str
    entity: str


class TenantSalesSeriesResponse(BaseModel):
    date: list[str]
    count: list[int]
    sum: list[str]


class TenantTotalsResponse(BaseModel):
    products: int
    sales_all_time: int
    debts_open_count: int
    customers_served: int


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
    city: str | None = None
    logo: str = ""
    last_login_at: str | None = None
    health: str = ""
    sales_7d: int = 0
    sales_30d: int = 0
    sales_sum_30d: str = "0"
    sales_series_30d: TenantSalesSeriesResponse | None = None
    users: list[TenantUserResponse] = []
    warehouses: list[TenantWarehouseResponse] = []
    top_products: list[TenantTopProductResponse] = []
    storefront: TenantStorefrontResponse | None = None
    recent_activity: list[TenantActivityResponse] = []
    totals: TenantTotalsResponse | None = None

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
            city=d.city,
            logo=d.logo,
            last_login_at=d.last_login_at,
            health=d.health,
            sales_7d=d.sales_7d,
            sales_30d=d.sales_30d,
            sales_sum_30d=d.sales_sum_30d,
            sales_series_30d=(
                TenantSalesSeriesResponse(**asdict(d.sales_series_30d))
                if d.sales_series_30d
                else None
            ),
            users=[TenantUserResponse(**asdict(u)) for u in d.users],
            warehouses=[TenantWarehouseResponse(**asdict(w)) for w in d.warehouses],
            top_products=[TenantTopProductResponse(**asdict(t)) for t in d.top_products],
            storefront=(
                TenantStorefrontResponse(**asdict(d.storefront)) if d.storefront else None
            ),
            recent_activity=[TenantActivityResponse(**asdict(a)) for a in d.recent_activity],
            totals=TenantTotalsResponse(**asdict(d.totals)) if d.totals else None,
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
    # v2: None там, где значение недоступно (нет расширения БД, нет файла
    # статуса) — фронт показывает «нет данных», а не ноль
    load_avg: list[float] | None = None
    disk_free_percent: float | None = None
    app: dict | None = None
    db: dict | None = None
    redis: dict | None = None
    uploads: dict | None = None
    api: dict | None = None
    backup: dict | None = None
    tls: dict | None = None

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
            load_avg=result.load_avg,
            disk_free_percent=result.disk_free_percent,
            app=asdict(result.app) if result.app else None,
            db=asdict(result.db) if result.db else None,
            redis=asdict(result.redis) if result.redis else None,
            uploads=asdict(result.uploads) if result.uploads else None,
            api=asdict(result.api) if result.api else None,
            backup=result.backup,
            tls=result.tls,
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


class OverviewShopsResponse(BaseModel):
    total: int
    active_7d: int
    active_30d: int
    new_7d: int
    new_30d: int
    suspended: int
    storefront_on: int


class OverviewUsersResponse(BaseModel):
    total: int
    active_7d: int


class OverviewCustomersResponse(BaseModel):
    total: int
    new_7d: int


class OverviewSalesResponse(BaseModel):
    today_count: int
    today_sum: Decimal
    d7_count: int
    d7_sum: Decimal
    d30_count: int
    d30_sum: Decimal


class OverviewDebtsResponse(BaseModel):
    """Без разбивки по клиентам — админ платформы видит агрегат, не чужой бизнес."""

    open_count: int
    open_sum: Decimal


class OverviewStorefrontResponse(BaseModel):
    requests_7d: int
    accepted_7d: int


class OverviewSeriesResponse(BaseModel):
    """Массивы одной длины: date[i] соответствует остальным полям по индексу."""

    date: list[str]
    new_shops: list[int]
    sales_count: list[int]
    active_shops: list[int]


class OverviewDeltasResponse(BaseModel):
    """null — в прошлом периоде был ноль: дельту показывать не от чего."""

    sales_count_30d: float | None
    sales_sum_30d: float | None
    new_shops_7d: float | None
    storefront_requests_7d: float | None


class AttentionShopResponse(BaseModel):
    id: int
    name: str
    last_sale_at: str | None
    created_at: str


class AttentionErrorResponse(BaseModel):
    signature: str
    type: str
    path: str
    count_24h: int


class OverviewAttentionResponse(BaseModel):
    went_quiet: list[AttentionShopResponse]
    never_sold: list[AttentionShopResponse]
    top_errors: list[AttentionErrorResponse]


class RecentShopResponse(BaseModel):
    id: int
    name: str
    city: str | None
    created_at: str
    storefront_enabled: bool


class PlatformOverviewResponse(BaseModel):
    shops: OverviewShopsResponse
    users: OverviewUsersResponse
    customers: OverviewCustomersResponse
    sales: OverviewSalesResponse
    debts: OverviewDebtsResponse
    storefront: OverviewStorefrontResponse
    series_30d: OverviewSeriesResponse
    deltas: OverviewDeltasResponse
    attention: OverviewAttentionResponse
    recent_shops: list[RecentShopResponse]

    @classmethod
    def from_result(cls, result: PlatformOverview) -> "PlatformOverviewResponse":
        return cls(
            shops=OverviewShopsResponse(**asdict(result.shops)),
            users=OverviewUsersResponse(**asdict(result.users)),
            customers=OverviewCustomersResponse(**asdict(result.customers)),
            sales=OverviewSalesResponse(**asdict(result.sales)),
            debts=OverviewDebtsResponse(**asdict(result.debts)),
            storefront=OverviewStorefrontResponse(**asdict(result.storefront)),
            series_30d=OverviewSeriesResponse(**asdict(result.series_30d)),
            deltas=OverviewDeltasResponse(**asdict(result.deltas)),
            attention=OverviewAttentionResponse(
                went_quiet=[AttentionShopResponse(**asdict(s)) for s in result.attention.went_quiet],
                never_sold=[AttentionShopResponse(**asdict(s)) for s in result.attention.never_sold],
                top_errors=[AttentionErrorResponse(**asdict(e)) for e in result.attention.top_errors],
            ),
            recent_shops=[RecentShopResponse(**asdict(s)) for s in result.recent_shops],
        )


class ErrorGroupResponse(BaseModel):
    """Группа одинаковых ошибок: числовые сегменты пути схлопнуты, так что
    /api/products/17 и /api/products/42 — одна строка, а не две."""

    signature: str
    type: str
    path: str
    method: str
    count_24h: int
    count_7d: int
    first_at: str
    last_at: str
    sample_id: int
    resolved: bool


class ErrorEntryResponse(BaseModel):
    """Отдельная запись. Персональных данных нет: ни тела запроса, ни
    заголовков, ни параметров — только техническая информация."""

    id: int
    created_at: str
    method: str
    path: str
    error_type: str
    message: str
    status_code: int | None
    tenant_id: int | None
    stack: str
    resolved_at: str | None


class FeedbackItemResponse(BaseModel):
    """Обращение из кабинета: кто, откуда и что — чтобы не переспрашивать."""

    id: int
    topic: str
    text: str
    photos: list[str]
    page: str
    user_agent: str
    app_version: str
    created_at: datetime
    resolved_at: datetime | None
    tenant_id: int
    shop_name: str
    author_name: str
    author_phone: str
    author_role: str


class FeedbackListResponse(BaseModel):
    items: list[FeedbackItemResponse]
    total: int
    new_count: int
