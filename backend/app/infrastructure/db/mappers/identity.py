from app.domain.common.phone import Phone
from app.domain.identity.entities import Tenant, User, Warehouse
from app.infrastructure.db.models.identity import TenantModel, UserModel, WarehouseModel


class TenantMapper:
    @staticmethod
    def to_orm(tenant: Tenant) -> TenantModel:
        return TenantModel(
            name=tenant.name,
            slug=tenant.slug,
            storefront_enabled=tenant.storefront_enabled,
            owner_telegram_chat_id=tenant.owner_telegram_chat_id,
            summary_daily_enabled=tenant.summary_daily_enabled,
            summary_weekly_enabled=tenant.summary_weekly_enabled,
            summary_monthly_enabled=tenant.summary_monthly_enabled,
            summary_daily_hour_msk=tenant.summary_daily_hour_msk,
        )

    @staticmethod
    def to_entity(model: TenantModel) -> Tenant:
        return Tenant(
            id=model.id,
            name=model.name,
            slug=model.slug,
            storefront_enabled=model.storefront_enabled,
            owner_telegram_chat_id=model.owner_telegram_chat_id,
            summary_daily_enabled=model.summary_daily_enabled,
            summary_weekly_enabled=model.summary_weekly_enabled,
            summary_monthly_enabled=model.summary_monthly_enabled,
            summary_daily_hour_msk=model.summary_daily_hour_msk,
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
            token_version=model.token_version,
        )


class WarehouseMapper:
    @staticmethod
    def to_orm(warehouse: Warehouse, tenant_id: int) -> WarehouseModel:
        return WarehouseModel(
            tenant_id=tenant_id, name=warehouse.name, address=warehouse.address
        )

    @staticmethod
    def to_entity(model: WarehouseModel, assigned_user_ids: list[int] | None = None) -> Warehouse:
        return Warehouse(
            id=model.id,
            name=model.name,
            address=model.address,
            assigned_user_ids=assigned_user_ids or [],
        )
