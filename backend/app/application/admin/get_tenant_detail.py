from dataclasses import dataclass

from sqlalchemy import func, select

from app.domain.identity.entities import Role
from app.infrastructure.db.models.catalog import ProductModel
from app.infrastructure.db.models.identity import TenantModel, UserModel, WarehouseModel
from app.infrastructure.db.models.sales import SaleModel


@dataclass(frozen=True)
class TenantOwnerInfo:
    name: str
    phone: str


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
        )
