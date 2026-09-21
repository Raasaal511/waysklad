from dataclasses import dataclass, field

from sqlalchemy import func, select, text

from datetime import datetime, timedelta, timezone

from app.domain.identity.entities import Role
from app.domain.platform.health import tenant_health
from app.infrastructure.db.models.audit import AuditLogModel
from app.infrastructure.db.models.debts import DebtModel, DebtRepaymentModel
from app.infrastructure.db.models.inventory import StockItemModel
from app.infrastructure.db.models.reviews import ReviewModel
from app.infrastructure.db.models.storefront import StorefrontRequestModel
from app.infrastructure.db.models.catalog import ProductModel
from app.infrastructure.db.models.identity import TenantModel, UserModel, WarehouseModel
from app.infrastructure.db.models.sales import SaleLineModel, SaleModel


@dataclass(frozen=True)
class TenantOwnerInfo:
    name: str
    phone: str


@dataclass(frozen=True)
class TenantUserInfo:
    id: int
    name: str
    role: str
    is_active: bool
    last_login_at: str | None


@dataclass(frozen=True)
class TenantWarehouseInfo:
    id: int
    name: str
    address: str
    show_on_storefront: bool
    positions_count: int


@dataclass(frozen=True)
class TenantTopProduct:
    """Только название и счётчик: выручка и закупочные цены по товарам —
    содержимое чужого бизнеса, админу платформы они не нужны."""

    id: int
    name: str
    sold_30d: str


@dataclass(frozen=True)
class TenantStorefrontInfo:
    enabled: bool
    slug: str | None
    products_on_storefront: int
    requests_30d: int
    reviews_count: int


@dataclass(frozen=True)
class TenantActivityEntry:
    at: str
    actor_name: str
    action: str
    entity: str


@dataclass(frozen=True)
class TenantSalesSeries:
    date: list[str]
    count: list[int]
    sum: list[str]


@dataclass(frozen=True)
class TenantTotals:
    products: int
    sales_all_time: int
    debts_open_count: int
    customers_served: int


@dataclass(frozen=True)
class TenantDetail:
    id: int
    name: str
    slug: str | None
    storefront_enabled: bool
    is_suspended: bool
    is_verified: bool
    created_at: str
    owner: TenantOwnerInfo | None
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
    sales_series_30d: TenantSalesSeries | None = None
    users: list[TenantUserInfo] = field(default_factory=list)
    warehouses: list[TenantWarehouseInfo] = field(default_factory=list)
    top_products: list[TenantTopProduct] = field(default_factory=list)
    storefront: TenantStorefrontInfo | None = None
    recent_activity: list[TenantActivityEntry] = field(default_factory=list)
    totals: TenantTotals | None = None


async def get_tenant_detail(session_factory, tenant_id: int) -> TenantDetail | None:
    async with session_factory() as session:
        tenant = (
            await session.execute(select(TenantModel).where(TenantModel.id == tenant_id))
        ).scalar_one_or_none()
        if tenant is None:
            return None

        owner_row = (
            await session.execute(
                select(UserModel.name, UserModel.phone).where(
                    UserModel.tenant_id == tenant_id,
                    UserModel.role == Role.OWNER,
                    UserModel.is_active.is_(True),
                )
            )
        ).first()
        owner = TenantOwnerInfo(name=owner_row.name, phone=owner_row.phone) if owner_row else None

        users_count = (
            await session.execute(
                select(func.count())
                .select_from(UserModel)
                .where(UserModel.tenant_id == tenant_id, UserModel.is_active.is_(True))
            )
        ).scalar_one()
        products_count = (
            await session.execute(
                select(func.count())
                .select_from(ProductModel)
                .where(ProductModel.tenant_id == tenant_id)
            )
        ).scalar_one()
        warehouses_count = (
            await session.execute(
                select(func.count())
                .select_from(WarehouseModel)
                .where(WarehouseModel.tenant_id == tenant_id)
            )
        ).scalar_one()
        last_sale_at = (
            await session.execute(
                select(func.max(SaleModel.created_at)).where(SaleModel.tenant_id == tenant_id)
            )
        ).scalar_one()

        now = datetime.now(timezone.utc)
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)

        sales_row = (
            await session.execute(
                select(
                    func.count(SaleModel.id).filter(SaleModel.created_at >= d7),
                    func.count(SaleModel.id).filter(SaleModel.created_at >= d30),
                    func.coalesce(
                        func.sum(SaleModel.total).filter(SaleModel.created_at >= d30), 0
                    ),
                    func.count(SaleModel.id),
                ).where(SaleModel.tenant_id == tenant_id)
            )
        ).one()

        return TenantDetail(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            storefront_enabled=tenant.storefront_enabled,
            is_suspended=tenant.is_suspended,
            is_verified=tenant.is_verified,
            created_at=tenant.created_at.isoformat(),
            owner=owner,
            users_count=users_count,
            products_count=products_count,
            warehouses_count=warehouses_count,
            last_sale_at=last_sale_at.isoformat() if last_sale_at else None,
            city=tenant.city,
            logo=tenant.logo,
            last_login_at=_iso(await _last_login(session, tenant_id)),
            health=tenant_health(tenant.created_at, last_sale_at, now).value,
            sales_7d=sales_row[0],
            sales_30d=sales_row[1],
            sales_sum_30d=str(sales_row[2]),
            sales_series_30d=await _sales_series(session, tenant_id, d30),
            users=await _users(session, tenant_id),
            warehouses=await _warehouses(session, tenant_id),
            top_products=await _top_products(session, tenant_id, d30),
            storefront=await _storefront(session, tenant, d30),
            recent_activity=await _recent_activity(session, tenant_id),
            totals=TenantTotals(
                products=products_count,
                sales_all_time=sales_row[3],
                debts_open_count=await _open_debts_count(session, tenant_id),
                customers_served=await _customers_served(session, tenant_id),
            ),
        )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def _last_login(session, tenant_id: int) -> datetime | None:
    return (
        await session.execute(
            select(func.max(UserModel.last_login_at)).where(UserModel.tenant_id == tenant_id)
        )
    ).scalar_one()


async def _sales_series(session, tenant_id: int, since) -> TenantSalesSeries:
    """Ряд по дням: generate_series, чтобы дни без продаж остались нулями —
    иначе график схлопнет простои и покажет неправду."""
    rows = (
        await session.execute(
            text(
                """
                WITH days AS (
                    SELECT generate_series(
                        date_trunc('day', :since AT TIME ZONE 'UTC'),
                        date_trunc('day', now() AT TIME ZONE 'UTC'),
                        interval '1 day'
                    )::date AS day
                )
                SELECT days.day,
                       COALESCE(s.cnt, 0),
                       COALESCE(s.total, 0)
                FROM days
                LEFT JOIN (
                    SELECT date_trunc('day', created_at)::date AS day,
                           COUNT(*) AS cnt,
                           SUM(total) AS total
                    FROM sales
                    WHERE tenant_id = :tenant_id
                    GROUP BY 1
                ) s ON s.day = days.day
                ORDER BY days.day
                """
            ),
            {"tenant_id": tenant_id, "since": since},
        )
    ).all()
    return TenantSalesSeries(
        date=[r[0].isoformat() for r in rows],
        count=[r[1] for r in rows],
        sum=[str(r[2]) for r in rows],
    )


async def _users(session, tenant_id: int) -> list[TenantUserInfo]:
    rows = (
        await session.execute(
            select(
                UserModel.id,
                UserModel.name,
                UserModel.role,
                UserModel.is_active,
                UserModel.last_login_at,
            )
            .where(UserModel.tenant_id == tenant_id)
            .order_by(UserModel.id)
        )
    ).all()
    # телефоны сотрудников сюда не попадают — это персональные данные
    return [
        TenantUserInfo(
            id=r[0], name=r[1], role=r[2].value, is_active=r[3], last_login_at=_iso(r[4])
        )
        for r in rows
    ]


async def _warehouses(session, tenant_id: int) -> list[TenantWarehouseInfo]:
    positions = (
        select(
            StockItemModel.warehouse_id.label("warehouse_id"),
            func.count(StockItemModel.id).label("cnt"),
        )
        .where(StockItemModel.tenant_id == tenant_id, StockItemModel.quantity > 0)
        .group_by(StockItemModel.warehouse_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(
                WarehouseModel.id,
                WarehouseModel.name,
                WarehouseModel.address,
                WarehouseModel.show_on_storefront,
                func.coalesce(positions.c.cnt, 0),
            )
            .outerjoin(positions, positions.c.warehouse_id == WarehouseModel.id)
            .where(WarehouseModel.tenant_id == tenant_id)
            .order_by(WarehouseModel.id)
        )
    ).all()
    return [
        TenantWarehouseInfo(
            id=r[0], name=r[1], address=r[2] or "", show_on_storefront=r[3], positions_count=r[4]
        )
        for r in rows
    ]


async def _top_products(session, tenant_id: int, since) -> list[TenantTopProduct]:
    rows = (
        await session.execute(
            select(
                ProductModel.id,
                ProductModel.name,
                func.coalesce(func.sum(SaleLineModel.quantity), 0).label("sold"),
            )
            .join(SaleLineModel, SaleLineModel.product_id == ProductModel.id)
            .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
            .where(SaleModel.tenant_id == tenant_id, SaleModel.created_at >= since)
            .group_by(ProductModel.id, ProductModel.name)
            .order_by(func.sum(SaleLineModel.quantity).desc())
            .limit(5)
        )
    ).all()
    return [TenantTopProduct(id=r[0], name=r[1], sold_30d=str(r[2])) for r in rows]


async def _storefront(session, tenant, since) -> TenantStorefrontInfo:
    on_storefront = (
        await session.execute(
            select(func.count(ProductModel.id)).where(
                ProductModel.tenant_id == tenant.id,
                ProductModel.show_on_storefront.is_(True),
                ProductModel.is_active.is_(True),
            )
        )
    ).scalar_one()
    requests_30d = (
        await session.execute(
            select(func.count(StorefrontRequestModel.id)).where(
                StorefrontRequestModel.tenant_id == tenant.id,
                StorefrontRequestModel.created_at >= since,
            )
        )
    ).scalar_one()
    reviews_count = (
        await session.execute(
            select(func.count(ReviewModel.id)).where(ReviewModel.tenant_id == tenant.id)
        )
    ).scalar_one()
    return TenantStorefrontInfo(
        enabled=tenant.storefront_enabled,
        slug=tenant.slug,
        products_on_storefront=on_storefront,
        requests_30d=requests_30d,
        reviews_count=reviews_count,
    )


async def _recent_activity(session, tenant_id: int) -> list[TenantActivityEntry]:
    """Последние действия: кто, что и когда. Details намеренно не отдаём —
    там бывают суммы и имена клиентов магазина."""
    rows = (
        await session.execute(
            select(
                AuditLogModel.created_at,
                AuditLogModel.action,
                AuditLogModel.entity,
                UserModel.name,
            )
            .outerjoin(UserModel, UserModel.id == AuditLogModel.user_id)
            .where(AuditLogModel.tenant_id == tenant_id)
            .order_by(AuditLogModel.created_at.desc())
            .limit(20)
        )
    ).all()
    return [
        TenantActivityEntry(
            at=r[0].isoformat(), action=r[1], entity=r[2], actor_name=r[3] or ""
        )
        for r in rows
    ]


async def _open_debts_count(session, tenant_id: int) -> int:
    repaid = (
        select(
            DebtRepaymentModel.debt_id.label("debt_id"),
            func.sum(DebtRepaymentModel.amount).label("repaid"),
        )
        .group_by(DebtRepaymentModel.debt_id)
        .subquery()
    )
    remaining = DebtModel.amount - func.coalesce(repaid.c.repaid, 0)
    return (
        await session.execute(
            select(func.count(DebtModel.id))
            .select_from(DebtModel)
            .outerjoin(repaid, repaid.c.debt_id == DebtModel.id)
            .where(DebtModel.tenant_id == tenant_id, remaining > 0)
        )
    ).scalar_one()


async def _customers_served(session, tenant_id: int) -> int:
    """Сколько разных покупателей оставляли заявки — счётчик, без списка."""
    return (
        await session.execute(
            select(func.count(func.distinct(StorefrontRequestModel.customer_id))).where(
                StorefrontRequestModel.tenant_id == tenant_id,
                StorefrontRequestModel.customer_id.is_not(None),
            )
        )
    ).scalar_one()
