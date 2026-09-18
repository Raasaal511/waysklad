from __future__ import annotations

from sqlalchemy import delete, select

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
from app.infrastructure.db.models.identity import (
    TenantModel,
    UserModel,
    WarehouseAssignmentModel,
    WarehouseModel,
)
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
        model.name = tenant.name
        model.storefront_enabled = tenant.storefront_enabled
        model.owner_telegram_chat_id = tenant.owner_telegram_chat_id
        model.summary_daily_enabled = tenant.summary_daily_enabled
        model.summary_weekly_enabled = tenant.summary_weekly_enabled
        model.summary_monthly_enabled = tenant.summary_monthly_enabled
        model.summary_daily_hour_msk = tenant.summary_daily_hour_msk
        model.city = tenant.city
        model.logo = tenant.logo
        model.storefront_show_stock_qty = tenant.storefront_show_stock_qty
        model.storefront_description = tenant.storefront_description
        model.contact_phone = tenant.contact_phone
        model.contact_whatsapp = tenant.contact_whatsapp
        model.contact_telegram = tenant.contact_telegram
        model.storefront_min_order_total = tenant.storefront_min_order_total
        model.policy_refund_money = tenant.policy_refund_money
        model.policy_payment = tenant.policy_payment
        model.policy_delivery = tenant.policy_delivery
        model.policy_returns = tenant.policy_returns
        # is_verified намеренно не трогаем здесь — меняется только через
        # set_tenant_verified (админ), владелец через save() повлиять не может
        await self._session.flush()
        return tenant

    async def get_by_slug(self, slug: str) -> Tenant | None:
        model = (
            await self._session.execute(select(TenantModel).where(TenantModel.slug == slug))
        ).scalar_one_or_none()
        return TenantMapper.to_entity(model) if model else None

    async def get_by_owner_chat_id(self, chat_id: str) -> Tenant | None:
        model = (
            await self._session.execute(
                select(TenantModel).where(TenantModel.owner_telegram_chat_id == chat_id)
            )
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

    async def get(self, user_id: int) -> User:
        model = (
            await self._session.execute(
                select(UserModel).where(
                    UserModel.id == user_id, UserModel.tenant_id == self._tenant
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Пользователь {user_id} не найден")
        return UserMapper.to_entity(model)

    async def get_by_phone(self, phone: str) -> User | None:
        """Без фильтра по tenant: при логине магазин ещё неизвестен."""
        model = (
            await self._session.execute(select(UserModel).where(UserModel.phone == phone))
        ).scalar_one_or_none()
        return UserMapper.to_entity(model) if model else None

    async def get_token_version(self, user_id: int) -> int | None:
        row = (
            await self._session.execute(
                select(UserModel.token_version).where(
                    UserModel.id == user_id,
                    UserModel.tenant_id == self._tenant,
                    UserModel.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        return row

    async def list_by_tenant(self) -> list[User]:
        models = (
            await self._session.execute(
                select(UserModel)
                .where(UserModel.tenant_id == self._tenant)
                .order_by(UserModel.id)
            )
        ).scalars()
        return [UserMapper.to_entity(m) for m in models]

    async def save(self, user: User) -> User:
        model = (
            await self._session.execute(
                select(UserModel).where(
                    UserModel.id == user.id, UserModel.tenant_id == self._tenant
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Пользователь {user.id} не найден")
        model.name = user.name
        model.role = user.role
        model.is_active = user.is_active
        model.password_hash = user.password_hash
        model.token_version = user.token_version
        await self._session.flush()
        return user


class SqlAlchemyWarehouseRepository(SqlAlchemyRepository, IWarehouseRepository):
    async def add(self, warehouse: Warehouse) -> Warehouse:
        model = WarehouseMapper.to_orm(warehouse, self._tenant)
        self._session.add(model)
        await self._session.flush()
        warehouse.id = model.id
        if warehouse.assigned_user_ids:
            await self.set_assignments(model.id, warehouse.assigned_user_ids)
        return warehouse

    async def update_details(
        self, warehouse_id: int, name: str, address: str, show_on_storefront: bool = False
    ) -> Warehouse:
        model = (
            await self._session.execute(
                select(WarehouseModel).where(
                    WarehouseModel.id == warehouse_id, WarehouseModel.tenant_id == self._tenant
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Склад {warehouse_id} не найден")
        model.name = name
        model.address = address
        model.show_on_storefront = show_on_storefront
        await self._session.flush()
        return await self.get(warehouse_id)

    async def set_photo(self, warehouse_id: int, photo: str) -> Warehouse:
        model = (
            await self._session.execute(
                select(WarehouseModel).where(
                    WarehouseModel.id == warehouse_id, WarehouseModel.tenant_id == self._tenant
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Склад {warehouse_id} не найден")
        model.photo = photo
        await self._session.flush()
        return await self.get(warehouse_id)

    async def _assigned_user_ids(self, warehouse_ids: list[int]) -> dict[int, list[int]]:
        if not warehouse_ids:
            return {}
        # WarehouseAssignmentModel сам не хранит tenant_id (чисто связующая таблица
        # warehouse_id<->user_id) — join на WarehouseModel.tenant_id страхует от
        # утечки, если warehouse_ids когда-нибудь придёт без предварительной
        # tenant-проверки выше по стеку
        rows = (
            await self._session.execute(
                select(
                    WarehouseAssignmentModel.warehouse_id, WarehouseAssignmentModel.user_id
                )
                .join(WarehouseModel, WarehouseModel.id == WarehouseAssignmentModel.warehouse_id)
                .where(
                    WarehouseAssignmentModel.warehouse_id.in_(warehouse_ids),
                    WarehouseModel.tenant_id == self._tenant,
                )
            )
        ).all()
        result: dict[int, list[int]] = {wid: [] for wid in warehouse_ids}
        for warehouse_id, user_id in rows:
            result[warehouse_id].append(user_id)
        return result

    async def get(self, warehouse_id: int) -> Warehouse:
        model = (
            await self._session.execute(
                select(WarehouseModel).where(
                    WarehouseModel.id == warehouse_id, WarehouseModel.tenant_id == self._tenant
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Склад {warehouse_id} не найден")
        assigned = await self._assigned_user_ids([warehouse_id])
        return WarehouseMapper.to_entity(model, assigned.get(warehouse_id, []))

    async def list(self) -> list[Warehouse]:
        models = (
            await self._session.execute(
                select(WarehouseModel)
                .where(WarehouseModel.tenant_id == self._tenant)
                .order_by(WarehouseModel.id)
            )
        ).scalars().all()
        assigned = await self._assigned_user_ids([m.id for m in models])
        return [WarehouseMapper.to_entity(m, assigned.get(m.id, [])) for m in models]

    async def list_for_user(self, user_id: int) -> list[Warehouse]:
        models = (
            await self._session.execute(
                select(WarehouseModel)
                .join(
                    WarehouseAssignmentModel,
                    WarehouseAssignmentModel.warehouse_id == WarehouseModel.id,
                )
                .where(
                    WarehouseModel.tenant_id == self._tenant,
                    WarehouseAssignmentModel.user_id == user_id,
                )
                .order_by(WarehouseModel.id)
            )
        ).scalars().all()
        assigned = await self._assigned_user_ids([m.id for m in models])
        return [WarehouseMapper.to_entity(m, assigned.get(m.id, [])) for m in models]

    async def is_assigned(self, warehouse_id: int, user_id: int) -> bool:
        result = (
            await self._session.execute(
                select(WarehouseAssignmentModel.id)
                .join(WarehouseModel, WarehouseModel.id == WarehouseAssignmentModel.warehouse_id)
                .where(
                    WarehouseAssignmentModel.warehouse_id == warehouse_id,
                    WarehouseAssignmentModel.user_id == user_id,
                    WarehouseModel.tenant_id == self._tenant,
                )
            )
        ).scalar_one_or_none()
        return result is not None

    async def set_assignments(self, warehouse_id: int, user_ids: list[int]) -> Warehouse:
        # get() уже кидает NotFoundError, если склад не принадлежит текущему
        # tenant — гарантирует, что warehouse_id ниже принадлежит tenant
        await self.get(warehouse_id)
        await self._session.execute(
            delete(WarehouseAssignmentModel).where(
                WarehouseAssignmentModel.warehouse_id == warehouse_id
            )
        )
        for user_id in set(user_ids):
            self._session.add(
                WarehouseAssignmentModel(warehouse_id=warehouse_id, user_id=user_id)
            )
        await self._session.flush()
        return await self.get(warehouse_id)

    async def add_assignment(self, warehouse_id: int, user_id: int) -> None:
        await self.get(warehouse_id)  # проверяет принадлежность tenant, кидает NotFoundError иначе
        already = (
            await self._session.execute(
                select(WarehouseAssignmentModel.id).where(
                    WarehouseAssignmentModel.warehouse_id == warehouse_id,
                    WarehouseAssignmentModel.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if already is not None:
            return
        self._session.add(
            WarehouseAssignmentModel(warehouse_id=warehouse_id, user_id=user_id)
        )
        await self._session.flush()

    async def set_user_assignments(self, user_id: int, warehouse_ids: list[int]) -> None:
        # только назначения на склады текущего tenant — если warehouse_ids
        # когда-нибудь придёт непровалидированным, чужой склад тут не пройдёт
        tenant_warehouse_ids = {
            wid
            for wid in (
                await self._session.execute(
                    select(WarehouseModel.id).where(
                        WarehouseModel.id.in_(warehouse_ids),
                        WarehouseModel.tenant_id == self._tenant,
                    )
                )
            ).scalars()
        }
        await self._session.execute(
            delete(WarehouseAssignmentModel).where(
                WarehouseAssignmentModel.user_id == user_id
            )
        )
        for warehouse_id in tenant_warehouse_ids:
            self._session.add(
                WarehouseAssignmentModel(warehouse_id=warehouse_id, user_id=user_id)
            )
        await self._session.flush()
