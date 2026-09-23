from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.auth.change_password import ChangePasswordCommand
from app.application.auth.connect_telegram import ConnectTelegramCommand
from app.application.auth.create_employee import CreateEmployeeCommand
from app.application.auth.login import LoginCommand
from app.application.auth.register_shop import RegisterShopCommand
from app.application.auth.update_employee import UpdateEmployeeCommand
from app.application.auth.update_shop import UpdateShopCommand
from app.domain.identity.entities import Role, Tenant, User


class RegisterRequest(BaseModel):
    shop_name: str = Field(min_length=1, max_length=200)
    owner_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=5, max_length=20)
    password: str = Field(min_length=6, max_length=100)
    personal_data_consent: bool = False

    def to_command(self) -> RegisterShopCommand:
        return RegisterShopCommand(
            shop_name=self.shop_name,
            owner_name=self.owner_name,
            phone=self.phone,
            password=self.password,
            personal_data_consent=self.personal_data_consent,
        )


class LoginRequest(BaseModel):
    phone: str
    password: str

    def to_command(self) -> LoginCommand:
        return LoginCommand(phone=self.phone, password=self.password)


class CreateEmployeeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=5, max_length=20)
    password: str = Field(min_length=6, max_length=100)
    role: Role
    warehouse_ids: list[int] = Field(default_factory=list)

    def to_command(self) -> CreateEmployeeCommand:
        return CreateEmployeeCommand(
            name=self.name, phone=self.phone, password=self.password, role=self.role,
            warehouse_ids=self.warehouse_ids,
        )


class UpdateEmployeeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: Role
    is_active: bool = True
    warehouse_ids: list[int] | None = None

    def to_command(self, user_id: int) -> UpdateEmployeeCommand:
        return UpdateEmployeeCommand(
            user_id=user_id, name=self.name, role=self.role, is_active=self.is_active,
            warehouse_ids=self.warehouse_ids,
        )


class UserResponse(BaseModel):
    id: int
    name: str
    phone: str
    role: Role
    is_active: bool = True
    warehouse_ids: list[int] = Field(default_factory=list)

    @classmethod
    def from_entity(cls, user: User, warehouse_ids: list[int] | None = None) -> "UserResponse":
        return cls(
            id=user.id, name=user.name, phone=str(user.phone), role=user.role,
            is_active=user.is_active, warehouse_ids=warehouse_ids or [],
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    shop_slug: str | None = None  # публичный URL витрины; заполнен только при регистрации


class ConnectTelegramRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=32)

    def to_command(self) -> ConnectTelegramCommand:
        return ConnectTelegramCommand(chat_id=self.chat_id)


class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str | None
    storefront_enabled: bool
    owner_telegram_chat_id: str | None
    summary_daily_enabled: bool
    summary_weekly_enabled: bool
    summary_monthly_enabled: bool
    summary_daily_hour_msk: int
    city: str | None
    is_verified: bool
    logo: str
    storefront_show_stock_qty: bool
    storefront_description: str
    contact_phone: str
    contact_whatsapp: str
    contact_telegram: str
    storefront_min_order_total: Decimal | None
    policy_refund_money: str
    policy_payment: str
    policy_delivery: str
    policy_returns: str

    @classmethod
    def from_entity(cls, tenant: Tenant) -> "TenantResponse":
        return cls(
            id=tenant.id, name=tenant.name,
            slug=tenant.slug,
            storefront_enabled=tenant.storefront_enabled,
            owner_telegram_chat_id=tenant.owner_telegram_chat_id,
            summary_daily_enabled=tenant.summary_daily_enabled,
            summary_weekly_enabled=tenant.summary_weekly_enabled,
            summary_monthly_enabled=tenant.summary_monthly_enabled,
            summary_daily_hour_msk=tenant.summary_daily_hour_msk,
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


class UpdateShopRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    summary_daily_enabled: bool | None = None
    summary_weekly_enabled: bool | None = None
    summary_monthly_enabled: bool | None = None
    summary_daily_hour_msk: int | None = Field(default=None, ge=0, le=23)
    storefront_enabled: bool | None = None
    city: str | None = None  # валидация по справочнику CITIES — в UpdateShopUseCase
    storefront_show_stock_qty: bool | None = None
    storefront_description: str | None = Field(default=None, max_length=500)
    contact_phone: str | None = None  # формат — в UpdateShopUseCase (Phone), "" сбрасывает
    contact_whatsapp: str | None = None
    contact_telegram: str | None = None  # username без "@", формат — в UpdateShopUseCase
    # null (явно переданный) — сбросить лимит; поле отсутствует в body — не трогать;
    # число — установить новое значение (см. clear_min_order_total в команде)
    storefront_min_order_total: Decimal | None = Field(default=None, ge=0)
    policy_refund_money: str | None = Field(default=None, max_length=5000)
    policy_payment: str | None = Field(default=None, max_length=5000)
    policy_delivery: str | None = Field(default=None, max_length=5000)
    policy_returns: str | None = Field(default=None, max_length=5000)

    def to_command(self) -> UpdateShopCommand:
        min_order_total_set = "storefront_min_order_total" in self.model_fields_set
        return UpdateShopCommand(
            name=self.name,
            summary_daily_enabled=self.summary_daily_enabled,
            summary_weekly_enabled=self.summary_weekly_enabled,
            summary_monthly_enabled=self.summary_monthly_enabled,
            summary_daily_hour_msk=self.summary_daily_hour_msk,
            storefront_enabled=self.storefront_enabled,
            city=self.city,
            storefront_show_stock_qty=self.storefront_show_stock_qty,
            storefront_description=self.storefront_description,
            contact_phone=self.contact_phone,
            contact_whatsapp=self.contact_whatsapp,
            contact_telegram=self.contact_telegram,
            clear_min_order_total=min_order_total_set and self.storefront_min_order_total is None,
            storefront_min_order_total=self.storefront_min_order_total,
            policy_refund_money=self.policy_refund_money,
            policy_payment=self.policy_payment,
            policy_delivery=self.policy_delivery,
            policy_returns=self.policy_returns,
        )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=6, max_length=100)

    def to_command(self) -> ChangePasswordCommand:
        return ChangePasswordCommand(
            current_password=self.current_password, new_password=self.new_password
        )
