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

    def to_command(self) -> RegisterShopCommand:
        return RegisterShopCommand(
            shop_name=self.shop_name,
            owner_name=self.owner_name,
            phone=self.phone,
            password=self.password,
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
        )


class UpdateShopRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    summary_daily_enabled: bool | None = None
    summary_weekly_enabled: bool | None = None
    summary_monthly_enabled: bool | None = None
    summary_daily_hour_msk: int | None = Field(default=None, ge=0, le=23)
    storefront_enabled: bool | None = None

    def to_command(self) -> UpdateShopCommand:
        return UpdateShopCommand(
            name=self.name,
            summary_daily_enabled=self.summary_daily_enabled,
            summary_weekly_enabled=self.summary_weekly_enabled,
            summary_monthly_enabled=self.summary_monthly_enabled,
            summary_daily_hour_msk=self.summary_daily_hour_msk,
            storefront_enabled=self.storefront_enabled,
        )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=6, max_length=100)

    def to_command(self) -> ChangePasswordCommand:
        return ChangePasswordCommand(
            current_password=self.current_password, new_password=self.new_password
        )
