"""Список магазинов платформы с агрегатами (A2).

Как и обзор, это кросс-тенантные запросы: они ходят по всем магазинам без
фильтра по tenant_id. Такой код живёт только здесь — в общих репозиториях
ему не место, иначе однажды он попадёт в пользовательский сценарий и один
магазин увидит данные другого.

Агрегаты считаются пачкой (GROUP BY tenant_id), а не по магазину за раз:
иначе список из N магазинов стоил бы N запросов на каждый показатель.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Select, func, or_, select

from app.domain.platform.health import TenantHealth, tenant_health
from app.infrastructure.db.models.catalog import ProductModel
from app.infrastructure.db.models.identity import TenantModel, UserModel, WarehouseModel
from app.infrastructure.db.models.sales import SaleModel
from app.infrastructure.db.models.storefront import StorefrontRequestModel
from app.infrastructure.db.models.debts import DebtModel, DebtRepaymentModel
from app.domain.identity.entities import Role

CACHE_TTL_SECONDS = 30
DEFAULT_LIMIT = 50


@dataclass(frozen=True)
class TenantListItem:
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
    # когда владелец последний раз работал в кабинете (не только вводил пароль)
    owner_last_seen_at: str | None
    sales_7d: int
    sales_30d: int
    sales_sum_30d: Decimal
    debts_open_count: int
    storefront_requests_30d: int
    health: str


@dataclass(frozen=True)
class TenantListResult:
    items: list[TenantListItem]
    total: int
    # счётчики для чипов фильтра — по всей платформе, не по текущей странице
    counts_by_health: dict[str, int]


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def list_tenants(
    session_factory,
    query: str = "",
    status: str = "all",
    storefront: str | None = None,
    sort: str = "last_activity",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> TenantListResult:
    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    async with session_factory() as session:
        tenants = (await session.execute(select(TenantModel))).scalars().all()
        if not tenants:
            return TenantListResult(items=[], total=0, counts_by_health={})

        sales = await _sales_aggregates(session, d7, d30)
        counts = await _entity_counts(session)
        owners = await _owners(session)
        logins = await _last_logins(session)
        debts = await _open_debts(session)
        requests = await _storefront_requests(session, d30)

        items: list[TenantListItem] = []
        for tenant in tenants:
            sale = sales.get(tenant.id)
            owner_name, owner_seen_at = owners.get(tenant.id, ("", None))
            last_sale_at = sale["last_at"] if sale else None
            health = tenant_health(tenant.created_at, last_sale_at, now)
            items.append(
                TenantListItem(
                    id=tenant.id,
                    name=tenant.name,
                    slug=tenant.slug,
                    city=tenant.city,
                    created_at=tenant.created_at.isoformat(),
                    is_suspended=tenant.is_suspended,
                    is_verified=tenant.is_verified,
                    storefront_enabled=tenant.storefront_enabled,
                    owner_name=owner_name,
                    users_count=counts.get(tenant.id, {}).get("users", 0),
                    warehouses_count=counts.get(tenant.id, {}).get("warehouses", 0),
                    products_count=counts.get(tenant.id, {}).get("products", 0),
                    last_sale_at=_to_iso(last_sale_at),
                    last_login_at=_to_iso(logins.get(tenant.id)),
                    owner_last_seen_at=_to_iso(owner_seen_at),
                    sales_7d=sale["count_7d"] if sale else 0,
                    sales_30d=sale["count_30d"] if sale else 0,
                    sales_sum_30d=sale["sum_30d"] if sale else Decimal("0"),
                    debts_open_count=debts.get(tenant.id, 0),
                    storefront_requests_30d=requests.get(tenant.id, 0),
                    health=health.value,
                )
            )

    counts_by_health = {h.value: 0 for h in TenantHealth}
    for item in items:
        counts_by_health[item.health] += 1

    items = _filter(items, query, status, storefront)
    items = _sort(items, sort)
    total = len(items)
    return TenantListResult(
        items=items[offset : offset + limit],
        total=total,
        counts_by_health=counts_by_health,
    )


def _filter(
    items: list[TenantListItem], query: str, status: str, storefront: str | None
) -> list[TenantListItem]:
    result = items
    if query:
        needle = query.strip().lower()
        result = [
            i
            for i in result
            if needle in i.name.lower()
            or (i.slug or "").lower().find(needle) >= 0
            or (i.city or "").lower().find(needle) >= 0
        ]
    if status and status != "all":
        if status == "suspended":
            result = [i for i in result if i.is_suspended]
        else:
            result = [i for i in result if i.health == status]
    if storefront == "on":
        result = [i for i in result if i.storefront_enabled]
    elif storefront == "off":
        result = [i for i in result if not i.storefront_enabled]
    return result


def _sort(items: list[TenantListItem], sort: str) -> list[TenantListItem]:
    if sort == "name":
        return sorted(items, key=lambda i: i.name.lower())
    if sort == "created_at":
        return sorted(items, key=lambda i: i.created_at, reverse=True)
    if sort == "sales_30d":
        return sorted(items, key=lambda i: i.sales_30d, reverse=True)
    # last_activity (по умолчанию): магазины без продаж уходят вниз
    return sorted(items, key=lambda i: (i.last_sale_at or ""), reverse=True)


async def _sales_aggregates(session, d7, d30) -> dict[int, dict]:
    rows = (
        await session.execute(
            select(
                SaleModel.tenant_id,
                func.max(SaleModel.created_at),
                func.count(SaleModel.id).filter(SaleModel.created_at >= d7),
                func.count(SaleModel.id).filter(SaleModel.created_at >= d30),
                func.coalesce(
                    func.sum(SaleModel.total).filter(SaleModel.created_at >= d30), 0
                ),
            ).group_by(SaleModel.tenant_id)
        )
    ).all()
    return {
        r[0]: {
            "last_at": r[1],
            "count_7d": r[2],
            "count_30d": r[3],
            "sum_30d": Decimal(r[4]),
        }
        for r in rows
    }


async def _entity_counts(session) -> dict[int, dict[str, int]]:
    """Счётчики сущностей: по запросу на таблицу, а не на магазин."""
    result: dict[int, dict[str, int]] = {}

    async def collect(model, key: str, extra_where=None) -> None:
        stmt: Select = select(model.tenant_id, func.count(model.id)).group_by(
            model.tenant_id
        )
        if extra_where is not None:
            stmt = stmt.where(extra_where)
        for tenant_id, count in (await session.execute(stmt)).all():
            result.setdefault(tenant_id, {})[key] = count

    await collect(UserModel, "users")
    await collect(WarehouseModel, "warehouses")
    await collect(ProductModel, "products", ProductModel.is_active.is_(True))
    return result


async def _owners(session) -> dict[int, tuple[str, datetime | None]]:
    rows = (
        await session.execute(
            select(UserModel.tenant_id, UserModel.name, UserModel.last_seen_at).where(
                UserModel.role == Role.OWNER
            )
        )
    ).all()
    # у магазина один владелец; если их несколько — берём первого попавшегося
    return {tenant_id: (name, seen) for tenant_id, name, seen in rows}


async def _last_logins(session) -> dict[int, datetime]:
    rows = (
        await session.execute(
            select(UserModel.tenant_id, func.max(UserModel.last_login_at)).group_by(
                UserModel.tenant_id
            )
        )
    ).all()
    return {tenant_id: at for tenant_id, at in rows if at is not None}


async def _open_debts(session) -> dict[int, int]:
    """Только количество открытых долгов: суммы по чужим клиентам админ
    платформы не видит (см. раздел о приватности в задаче)."""
    repaid = (
        select(
            DebtRepaymentModel.debt_id.label("debt_id"),
            func.sum(DebtRepaymentModel.amount).label("repaid"),
        )
        .group_by(DebtRepaymentModel.debt_id)
        .subquery()
    )
    remaining = DebtModel.amount - func.coalesce(repaid.c.repaid, 0)
    rows = (
        await session.execute(
            select(DebtModel.tenant_id, func.count(DebtModel.id))
            .select_from(DebtModel)
            .outerjoin(repaid, repaid.c.debt_id == DebtModel.id)
            .where(remaining > 0)
            .group_by(DebtModel.tenant_id)
        )
    ).all()
    return {tenant_id: count for tenant_id, count in rows}


async def _storefront_requests(session, d30) -> dict[int, int]:
    rows = (
        await session.execute(
            select(StorefrontRequestModel.tenant_id, func.count(StorefrontRequestModel.id))
            .where(StorefrontRequestModel.created_at >= d30)
            .group_by(StorefrontRequestModel.tenant_id)
        )
    ).all()
    return {tenant_id: count for tenant_id, count in rows}
