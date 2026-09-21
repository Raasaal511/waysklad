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
class PlatformOverview:
    shops: ShopsOverview
    users: UsersOverview
    customers: CustomersOverview
    sales: SalesOverview
    debts: DebtsOverview
    storefront: StorefrontOverview
    series_30d: OverviewSeries

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
        )


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

        return PlatformOverview(
            shops=shops,
            users=users,
            customers=customers,
            sales=sales,
            debts=debts,
            storefront=storefront,
            series_30d=series,
        )

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
