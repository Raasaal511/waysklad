from app.domain.common.phone import Phone
from app.domain.identity.entities import Tenant, User, Warehouse
from app.infrastructure.db.models.identity import TenantModel, UserModel, WarehouseModel


class TenantMapper:
    @staticmethod
    def to_orm(tenant: Tenant) -> TenantModel:
        return TenantModel(
            name=tenant.name,
            slug=tenant.slug,
            owner_telegram_chat_id=tenant.owner_telegram_chat_id,
        )

    @staticmethod
    def to_entity(model: TenantModel) -> Tenant:
        return Tenant(
            id=model.id,
            name=model.name,
            slug=model.slug,
            owner_telegram_chat_id=model.owner_telegram_chat_id,
        )


class UserMapper:
    @staticmethod
    def to_orm(user: User, tenant_id: int) -> UserModel:
        return UserModel(
            tenant_id=tenant_id,
            name=user.name,
            phone=str(user.phone),
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
        )

    @staticmethod
    def to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            name=model.name,
            phone=Phone(model.phone),
            role=model.role,
            password_hash=model.password_hash,
            is_active=model.is_active,
            tenant_id=model.tenant_id,
        )


class WarehouseMapper:
    @staticmethod
    def to_orm(warehouse: Warehouse, tenant_id: int) -> WarehouseModel:
        return WarehouseModel(
            tenant_id=tenant_id, name=warehouse.name, address=warehouse.address
        )

    @staticmethod
    def to_entity(model: WarehouseModel) -> Warehouse:
        return Warehouse(id=model.id, name=model.name, address=model.address)
