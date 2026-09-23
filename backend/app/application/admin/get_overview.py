"""Обзор платформы для админки (A1).

Кросс-тенантные агрегаты: запросы намеренно идут без фильтра по tenant_id,
чего обычный код делать не должен. Поэтому они живут здесь, в admin-use-case,
а не в общих репозиториях — иначе рано или поздно такой запрос переиспользуют
в пользовательском сценарии и один магазин увидит данные другого.

Всё считается в SQL одним проходом на показатель: платформа маленькая, но
цикл по магазинам с отдельным запросом на каждый — это N+1, который вырастет
вместе с числом магазинов.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, text

from app.domain.platform.health import ACTIVE_WITHIN, CHURNED_AFTER, NEW_GRACE_PERIOD
from app.infrastructure.db.models.customers import CustomerModel
from app.infrastructure.db.models.debts import DebtModel, DebtRepaymentModel
from app.infrastructure.db.models.identity import TenantModel, UserModel
from app.infrastructure.db.models.sales import SaleModel
from app.infrastructure.db.models.storefront import StorefrontRequestModel

# кеш живёт на роуте (см. presentation/admin/router.py) — как у /status
CACHE_TTL_SECONDS = 60
SERIES_DAYS = 30

# Россия не переходит на летнее время — фиксированный сдвиг, как в сводках бота
MSK_OFFSET = timedelta(hours=3)


@dataclass(frozen=True)
class ShopsOverview:
    total: int
    active_7d: int
    active_30d: int
    new_7d: int
    new_30d: int
    suspended: int
    storefront_on: int


@dataclass(frozen=True)
class UsersOverview:
    total: int
    active_7d: int


@dataclass(frozen=True)
class CustomersOverview:
    total: int
    new_7d: int


@dataclass(frozen=True)
class SalesOverview:
    today_count: int
    today_sum: Decimal
    d7_count: int
    d7_sum: Decimal
    d30_count: int
    d30_sum: Decimal


@dataclass(frozen=True)
class DebtsOverview:
    """Агрегат по платформе без разбивки по клиентам — админ не видит,
    кто и сколько должен конкретному магазину."""

    open_count: int
    open_sum: Decimal


@dataclass(frozen=True)
class StorefrontOverview:
    requests_7d: int
    accepted_7d: int


@dataclass(frozen=True)
class OverviewSeries:
    date: list[str]
    new_shops: list[int]
    sales_count: list[int]
    active_shops: list[int]


@dataclass(frozen=True)
class OverviewDeltas:
    """Изменение к предыдущему такому же периоду, в процентах.

    None — сравнивать не с чем: в прошлом периоде было ноль, и «рост на
    бесконечность» ничего не говорит. Фронт в этом случае дельту не рисует.
    """

    sales_count_30d: float | None
    sales_sum_30d: float | None
    new_shops_7d: float | None
    storefront_requests_7d: float | None


@dataclass(frozen=True)
class AttentionShop:
    """Магазин, на который стоит посмотреть: затих или так и не начал."""

    id: int
    name: str
    last_sale_at: str | None
    created_at: str


@dataclass(frozen=True)
class AttentionError:
    signature: str
    type: str
    path: str
    count_24h: int


@dataclass(frozen=True)
class OverviewAttention:
    """Три списка для блока «Требует внимания» на обзоре."""

    went_quiet: list[AttentionShop]
    never_sold: list[AttentionShop]
    top_errors: list[AttentionError]


@dataclass(frozen=True)
class RecentShop:
    id: int
    name: str
    city: str | None
    created_at: str
    storefront_enabled: bool


@dataclass(frozen=True)
class PlatformOverview:
    shops: ShopsOverview
    users: UsersOverview
    customers: CustomersOverview
    sales: SalesOverview
    debts: DebtsOverview
    storefront: StorefrontOverview
    series_30d: OverviewSeries
    deltas: OverviewDeltas
    attention: OverviewAttention
    recent_shops: list[RecentShop]

    def to_json(self) -> dict:
        return {
            "shops": self.shops.__dict__,
            "users": self.users.__dict__,
            "customers": self.customers.__dict__,
            "sales": {
                "today_count": self.sales.today_count,
                "today_sum": str(self.sales.today_sum),
                "d7_count": self.sales.d7_count,
                "d7_sum": str(self.sales.d7_sum),
                "d30_count": self.sales.d30_count,
                "d30_sum": str(self.sales.d30_sum),
            },
            "debts": {
                "open_count": self.debts.open_count,
                "open_sum": str(self.debts.open_sum),
            },
            "storefront": self.storefront.__dict__,
            "series_30d": self.series_30d.__dict__,
            "deltas": self.deltas.__dict__,
            "attention": {
                "went_quiet": [s.__dict__ for s in self.attention.went_quiet],
                "never_sold": [s.__dict__ for s in self.attention.never_sold],
                "top_errors": [e.__dict__ for e in self.attention.top_errors],
            },
            "recent_shops": [s.__dict__ for s in self.recent_shops],
        }

    @classmethod
    def from_json(cls, d: dict) -> "PlatformOverview":
        return cls(
            shops=ShopsOverview(**d["shops"]),
            users=UsersOverview(**d["users"]),
            customers=CustomersOverview(**d["customers"]),
            sales=SalesOverview(
                today_count=d["sales"]["today_count"],
                today_sum=Decimal(d["sales"]["today_sum"]),
                d7_count=d["sales"]["d7_count"],
                d7_sum=Decimal(d["sales"]["d7_sum"]),
                d30_count=d["sales"]["d30_count"],
                d30_sum=Decimal(d["sales"]["d30_sum"]),
            ),
            debts=DebtsOverview(
                open_count=d["debts"]["open_count"],
                open_sum=Decimal(d["debts"]["open_sum"]),
            ),
            storefront=StorefrontOverview(**d["storefront"]),
            series_30d=OverviewSeries(**d["series_30d"]),
            deltas=OverviewDeltas(**d["deltas"]),
            attention=OverviewAttention(
                went_quiet=[AttentionShop(**s) for s in d["attention"]["went_quiet"]],
                never_sold=[AttentionShop(**s) for s in d["attention"]["never_sold"]],
                top_errors=[AttentionError(**e) for e in d["attention"]["top_errors"]],
            ),
            recent_shops=[RecentShop(**s) for s in d["recent_shops"]],
        )


def _percent_change(previous, current) -> float | None:
    """Изменение в процентах. None — в прошлом периоде был ноль: делить не на
    что, а «+∞%» читателю ничего не говорит."""
    prev = float(previous or 0)
    if prev == 0:
        return None
    return round((float(current or 0) - prev) / prev * 100, 1)


def msk_day_start_utc(now_utc: datetime) -> datetime:
    """Начало сегодняшних суток по Москве, выраженное в UTC — «сегодня»
    в админке считается так же, как в вечерних сводках бота."""
    msk_now = now_utc + MSK_OFFSET
    msk_midnight = msk_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return msk_midnight - MSK_OFFSET


async def get_platform_overview(session_factory) -> PlatformOverview:
    """Кеширование — на роуте (cached), как у /admin/status."""
    return await _Overview(session_factory).build()


class _Overview:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def build(self) -> PlatformOverview:
        now = datetime.now(timezone.utc)
        today_start = msk_day_start_utc(now)
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)

        async with self._session_factory() as session:
            shops = await self._shops(session, now, d7, d30)
            users = await self._users(session, d7)
            customers = await self._customers(session, d7)
            sales = await self._sales(session, today_start, d7, d30)
            debts = await self._debts(session)
            storefront = await self._storefront(session, d7)
            series = await self._series(session, d30)

            deltas = await self._deltas(session, now, d7, d30)
            attention = await self._attention(session, now)
            recent_shops = await self._recent_shops(session)

        return PlatformOverview(
            shops=shops,
            users=users,
            customers=customers,
            sales=sales,
            debts=debts,
            storefront=storefront,
            series_30d=series,
            deltas=deltas,
            attention=attention,
            recent_shops=recent_shops,
        )

    async def _deltas(self, session, now, d7, d30) -> OverviewDeltas:
        """Сравнение с предыдущим таким же периодом: последние 30 дней против
        30 дней до них, последние 7 против предыдущих 7."""
        prev_30_start = now - timedelta(days=60)
        prev_7_start = now - timedelta(days=14)

        sales_prev = (
            await session.execute(
                select(
                    func.count(SaleModel.id),
                    func.coalesce(func.sum(SaleModel.total), 0),
                ).where(SaleModel.created_at >= prev_30_start, SaleModel.created_at < d30)
            )
        ).one()
        sales_now = (
            await session.execute(
                select(
                    func.count(SaleModel.id),
                    func.coalesce(func.sum(SaleModel.total), 0),
                ).where(SaleModel.created_at >= d30)
            )
        ).one()

        shops_prev = (
            await session.execute(
                select(func.count(TenantModel.id)).where(
                    TenantModel.created_at >= prev_7_start, TenantModel.created_at < d7
                )
            )
        ).scalar_one()
        shops_now = (
            await session.execute(
                select(func.count(TenantModel.id)).where(TenantModel.created_at >= d7)
            )
        ).scalar_one()

        requests_prev = (
            await session.execute(
                select(func.count(StorefrontRequestModel.id)).where(
                    StorefrontRequestModel.created_at >= prev_7_start,
                    StorefrontRequestModel.created_at < d7,
                )
            )
        ).scalar_one()
        requests_now = (
            await session.execute(
                select(func.count(StorefrontRequestModel.id)).where(
                    StorefrontRequestModel.created_at >= d7
                )
            )
        ).scalar_one()

        return OverviewDeltas(
            sales_count_30d=_percent_change(sales_prev[0], sales_now[0]),
            sales_sum_30d=_percent_change(Decimal(sales_prev[1]), Decimal(sales_now[1])),
            new_shops_7d=_percent_change(shops_prev, shops_now),
            storefront_requests_7d=_percent_change(requests_prev, requests_now),
        )

    async def _attention(self, session, now) -> OverviewAttention:
        """Кого стоит посмотреть: затихшие, так и не начавшие, частые ошибки."""
        quiet_since = now - ACTIVE_WITHIN
        churn_since = now - CHURNED_AFTER
        grace_since = now - NEW_GRACE_PERIOD

        last_sale = (
            select(
                SaleModel.tenant_id.label("tenant_id"),
                func.max(SaleModel.created_at).label("last_at"),
            )
            .group_by(SaleModel.tenant_id)
            .subquery()
        )

        # продажи были, но давно: между «активен» и «бросил»
        quiet_rows = (
            await session.execute(
                select(
                    TenantModel.id,
                    TenantModel.name,
                    last_sale.c.last_at,
                    TenantModel.created_at,
                )
                .join(last_sale, last_sale.c.tenant_id == TenantModel.id)
                .where(
                    last_sale.c.last_at < quiet_since,
                    last_sale.c.last_at >= churn_since,
                    TenantModel.is_suspended.is_(False),
                )
                .order_by(last_sale.c.last_at.desc())
                .limit(5)
            )
        ).all()

        # зарегистрировались больше недели назад и не пробили ни одного чека
        never_rows = (
            await session.execute(
                select(TenantModel.id, TenantModel.name, TenantModel.created_at)
                .outerjoin(last_sale, last_sale.c.tenant_id == TenantModel.id)
                .where(
                    last_sale.c.last_at.is_(None),
                    TenantModel.created_at < grace_since,
                    TenantModel.is_suspended.is_(False),
                )
                .order_by(TenantModel.created_at.desc())
                .limit(5)
            )
        ).all()

        error_rows = (
            await session.execute(
                text(
                    """
                    SELECT signature, MAX(error_type) AS error_type, MAX(path) AS path,
                           COUNT(*) AS count_24h
                    FROM error_log
                    WHERE created_at >= :since AND resolved_at IS NULL
                    GROUP BY signature
                    ORDER BY count_24h DESC
                    LIMIT 3
                    """
                ),
                {"since": now - timedelta(days=1)},
            )
        ).all()

        return OverviewAttention(
            went_quiet=[
                AttentionShop(
                    id=r[0],
                    name=r[1],
                    last_sale_at=r[2].isoformat() if r[2] else None,
                    created_at=r[3].isoformat(),
                )
                for r in quiet_rows
            ],
            never_sold=[
                AttentionShop(
                    id=r[0], name=r[1], last_sale_at=None, created_at=r[2].isoformat()
                )
                for r in never_rows
            ],
            top_errors=[
                AttentionError(signature=r[0], type=r[1], path=r[2], count_24h=r[3])
                for r in error_rows
            ],
        )

    async def _recent_shops(self, session) -> list[RecentShop]:
        rows = (
            await session.execute(
                select(
                    TenantModel.id,
                    TenantModel.name,
                    TenantModel.city,
                    TenantModel.created_at,
                    TenantModel.storefront_enabled,
                )
                .order_by(TenantModel.created_at.desc())
                .limit(5)
            )
        ).all()
        return [
            RecentShop(
                id=r[0],
                name=r[1],
                city=r[2],
                created_at=r[3].isoformat(),
                storefront_enabled=r[4],
            )
            for r in rows
        ]

    async def _shops(self, session, now, d7, d30) -> ShopsOverview:
        row = (
            await session.execute(
                select(
                    func.count(TenantModel.id),
                    func.count(TenantModel.id).filter(TenantModel.created_at >= d7),
                    func.count(TenantModel.id).filter(TenantModel.created_at >= d30),
                    func.count(TenantModel.id).filter(TenantModel.is_suspended.is_(True)),
                    func.count(TenantModel.id).filter(
                        TenantModel.storefront_enabled.is_(True)
                    ),
                )
            )
        ).one()

        # «активен» = была хотя бы одна продажа за период
        active_7d = (
            await session.execute(
                select(func.count(func.distinct(SaleModel.tenant_id))).where(
                    SaleModel.created_at >= d7
                )
            )
        ).scalar_one()
        active_30d = (
            await session.execute(
                select(func.count(func.distinct(SaleModel.tenant_id))).where(
                    SaleModel.created_at >= d30
                )
            )
        ).scalar_one()

        return ShopsOverview(
            total=row[0],
            active_7d=active_7d,
            active_30d=active_30d,
            new_7d=row[1],
            new_30d=row[2],
            suspended=row[3],
            storefront_on=row[4],
        )

    async def _users(self, session, d7) -> UsersOverview:
        total = (await session.execute(select(func.count(UserModel.id)))).scalar_one()
        # «активен» для сотрудника — был вход за период
        active = (
            await session.execute(
                select(func.count(UserModel.id)).where(UserModel.last_login_at >= d7)
            )
        ).scalar_one()
        return UsersOverview(total=total, active_7d=active)

    async def _customers(self, session, d7) -> CustomersOverview:
        row = (
            await session.execute(
                select(
                    func.count(CustomerModel.id),
                    func.count(CustomerModel.id).filter(CustomerModel.created_at >= d7),
                )
            )
        ).one()
        return CustomersOverview(total=row[0], new_7d=row[1])

    async def _sales(self, session, today_start, d7, d30) -> SalesOverview:
        row = (
            await session.execute(
                select(
                    func.count(SaleModel.id).filter(SaleModel.created_at >= today_start),
                    func.coalesce(
                        func.sum(SaleModel.total).filter(
                            SaleModel.created_at >= today_start
                        ),
                        0,
                    ),
                    func.count(SaleModel.id).filter(SaleModel.created_at >= d7),
                    func.coalesce(
                        func.sum(SaleModel.total).filter(SaleModel.created_at >= d7), 0
                    ),
                    func.count(SaleModel.id).filter(SaleModel.created_at >= d30),
                    func.coalesce(
                        func.sum(SaleModel.total).filter(SaleModel.created_at >= d30), 0
                    ),
                )
            )
        ).one()
        return SalesOverview(
            today_count=row[0],
            today_sum=Decimal(row[1]),
            d7_count=row[2],
            d7_sum=Decimal(row[3]),
            d30_count=row[4],
            d30_sum=Decimal(row[5]),
        )

    async def _debts(self, session) -> DebtsOverview:
        # долг открыт, пока сумма погашений меньше суммы долга
        repaid = (
            select(
                DebtRepaymentModel.debt_id.label("debt_id"),
                func.sum(DebtRepaymentModel.amount).label("repaid"),
            )
            .group_by(DebtRepaymentModel.debt_id)
            .subquery()
        )
        remaining = DebtModel.amount - func.coalesce(repaid.c.repaid, 0)
        row = (
            await session.execute(
                select(func.count(DebtModel.id), func.coalesce(func.sum(remaining), 0))
                .select_from(DebtModel)
                .outerjoin(repaid, repaid.c.debt_id == DebtModel.id)
                .where(remaining > 0)
            )
        ).one()
        return DebtsOverview(open_count=row[0], open_sum=Decimal(row[1]))

    async def _storefront(self, session, d7) -> StorefrontOverview:
        row = (
            await session.execute(
                select(
                    func.count(StorefrontRequestModel.id).filter(
                        StorefrontRequestModel.created_at >= d7
                    ),
                    func.count(StorefrontRequestModel.id).filter(
                        StorefrontRequestModel.created_at >= d7,
                        StorefrontRequestModel.status == "accepted",
                    ),
                )
            )
        ).one()
        return StorefrontOverview(requests_7d=row[0], accepted_7d=row[1])

    async def _series(self, session, since) -> OverviewSeries:
        """Ряды по дням за 30 суток.

        generate_series, а не группировка в Python: дни без событий должны
        остаться в ряду нулями, иначе график «схлопнет» простои и покажет
        неправду.
        """
        query = text(
            """
            WITH days AS (
                SELECT generate_series(
                    date_trunc('day', :since AT TIME ZONE 'UTC'),
                    date_trunc('day', now() AT TIME ZONE 'UTC'),
                    interval '1 day'
                )::date AS day
            )
            SELECT
                days.day,
                COALESCE(s.sales_count, 0) AS sales_count,
                COALESCE(s.active_shops, 0) AS active_shops,
                COALESCE(t.new_shops, 0) AS new_shops
            FROM days
            LEFT JOIN (
                SELECT date_trunc('day', created_at)::date AS day,
                       COUNT(*) AS sales_count,
                       COUNT(DISTINCT tenant_id) AS active_shops
                FROM sales
                GROUP BY 1
            ) s ON s.day = days.day
            LEFT JOIN (
                SELECT date_trunc('day', created_at)::date AS day,
                       COUNT(*) AS new_shops
                FROM tenants
                GROUP BY 1
            ) t ON t.day = days.day
            ORDER BY days.day
            """
        )
        rows = (await session.execute(query, {"since": since})).all()
        return OverviewSeries(
            date=[r[0].isoformat() for r in rows],
            sales_count=[r[1] for r in rows],
            active_shops=[r[2] for r in rows],
            new_shops=[r[3] for r in rows],
        )
