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
            is_suspended=tenant.is_suspended,
            city=tenant.city,
            is_verified=tenant.is_verified,
            logo=tenant.logo,
            storefront_show_stock_qty=tenant.storefront_show_stock_qty,
            storefront_description=tenant.storefront_description,
            contact_phone=tenant.contact_phone,
            contact_whatsapp=tenant.contact_whatsapp,
            contact_telegram=tenant.contact_telegram,
            storefront_min_order_total=tenant.storefront_min_order_total,
            policy_refund_money=tenant.policy_refund_money,
            policy_payment=tenant.policy_payment,
            policy_delivery=tenant.policy_delivery,
            policy_returns=tenant.policy_returns,
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
            is_suspended=model.is_suspended,
            city=model.city,
            is_verified=model.is_verified,
            logo=model.logo,
            storefront_show_stock_qty=model.storefront_show_stock_qty,
            storefront_description=model.storefront_description,
            contact_phone=model.contact_phone,
            contact_whatsapp=model.contact_whatsapp,
            contact_telegram=model.contact_telegram,
            storefront_min_order_total=model.storefront_min_order_total,
            policy_refund_money=model.policy_refund_money,
            policy_payment=model.policy_payment,
            policy_delivery=model.policy_delivery,
            policy_returns=model.policy_returns,
            created_at=model.created_at,
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
            personal_data_consent_at=user.personal_data_consent_at,
            telegram_user_id=user.telegram_user_id,
            telegram_verified_at=user.telegram_verified_at,
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
            last_login_at=model.last_login_at,
            personal_data_consent_at=model.personal_data_consent_at,
            telegram_user_id=model.telegram_user_id,
            telegram_verified_at=model.telegram_verified_at,
        )


class WarehouseMapper:
    @staticmethod
    def to_orm(warehouse: Warehouse, tenant_id: int) -> WarehouseModel:
        return WarehouseModel(
            tenant_id=tenant_id,
            name=warehouse.name,
            address=warehouse.address,
            show_on_storefront=warehouse.show_on_storefront,
            photo=warehouse.photo,
        )

    @staticmethod
    def to_entity(model: WarehouseModel, assigned_user_ids: list[int] | None = None) -> Warehouse:
        return Warehouse(
            id=model.id,
            name=model.name,
            address=model.address,
            assigned_user_ids=assigned_user_ids or [],
            show_on_storefront=model.show_on_storefront,
            photo=model.photo,
        )
