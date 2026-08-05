from sqlalchemy import select

from app.domain.common.exceptions import NotFoundError
from app.domain.common.quantity import UNITS
from app.domain.identity.entities import Tenant, User, Warehouse
from app.domain.identity.repository import (
    ITenantRepository,
    IUserRepository,
    IWarehouseRepository,
)
from app.infrastructure.db.mappers.identity import TenantMapper, UserMapper, WarehouseMapper
from app.infrastructure.db.models.catalog import UnitModel
from app.infrastructure.db.models.identity import TenantModel, UserModel, WarehouseModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyTenantRepository(SqlAlchemyRepository, ITenantRepository):
    async def add(self, tenant: Tenant) -> Tenant:
        model = TenantMapper.to_orm(tenant)
        self._session.add(model)
        await self._session.flush()
        tenant.id = model.id
        # посев предустановленных единиц измерения для нового магазина
        for unit in UNITS.values():
            self._session.add(
                UnitModel(
                    tenant_id=model.id,
                    code=unit.code,
                    name=unit.name,
                    fractional=unit.fractional,
                )
            )
        await self._session.flush()
        return tenant

    async def get(self, tenant_id: int) -> Tenant:
        model = (
            await self._session.execute(select(TenantModel).where(TenantModel.id == tenant_id))
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Магазин {tenant_id} не найден")
        return TenantMapper.to_entity(model)

    async def save(self, tenant: Tenant) -> Tenant:
        model = (
            await self._session.execute(select(TenantModel).where(TenantModel.id == tenant.id))
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Магазин {tenant.id} не найден")
        model.owner_telegram_chat_id = tenant.owner_telegram_chat_id
        await self._session.flush()
        return tenant

    async def get_by_slug(self, slug: str) -> Tenant | None:
        model = (
            await self._session.execute(select(TenantModel).where(TenantModel.slug == slug))
        ).scalar_one_or_none()
        return TenantMapper.to_entity(model) if model else None

    async def list_all(self) -> list[Tenant]:
        models = (await self._session.execute(select(TenantModel))).scalars()
        return [TenantMapper.to_entity(m) for m in models]


class SqlAlchemyUserRepository(SqlAlchemyRepository, IUserRepository):
    async def add(self, user: User) -> User:
        model = UserMapper.to_orm(user, self._tenant)
        self._session.add(model)
        await self._session.flush()
        user.id = model.id
        user.tenant_id = model.tenant_id
        return user

    async def get_by_phone(self, phone: str) -> User | None:
        """Без фильтра по tenant: при логине магазин ещё неизвестен."""
        model = (
            await self._session.execute(select(UserModel).where(UserModel.phone == phone))
        ).scalar_one_or_none()
        return UserMapper.to_entity(model) if model else None

    async def list_by_tenant(self) -> list[User]:
        models = (
            await self._session.execute(
                select(UserModel)
                .where(UserModel.tenant_id == self._tenant)
                .order_by(UserModel.id)
            )
        ).scalars()
        return [UserMapper.to_entity(m) for m in models]


class SqlAlchemyWarehouseRepository(SqlAlchemyRepository, IWarehouseRepository):
    async def add(self, warehouse: Warehouse) -> Warehouse:
        model = WarehouseMapper.to_orm(warehouse, self._tenant)
        self._session.add(model)
        await self._session.flush()
        warehouse.id = model.id
        return warehouse

    async def list(self) -> list[Warehouse]:
        models = (
            await self._session.execute(
                select(WarehouseModel)
                .where(WarehouseModel.tenant_id == self._tenant)
                .order_by(WarehouseModel.id)
            )
        ).scalars()
        return [WarehouseMapper.to_entity(m) for m in models]
