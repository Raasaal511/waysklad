from pydantic import BaseModel, Field

from app.application.auth.connect_telegram import ConnectTelegramCommand
from app.application.auth.create_employee import CreateEmployeeCommand
from app.application.auth.login import LoginCommand
from app.application.auth.register_shop import RegisterShopCommand
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

    def to_command(self) -> CreateEmployeeCommand:
        return CreateEmployeeCommand(
            name=self.name, phone=self.phone, password=self.password, role=self.role
        )


class UserResponse(BaseModel):
    id: int
    name: str
    phone: str
    role: Role

    @classmethod
    def from_entity(cls, user: User) -> "UserResponse":
        return cls(id=user.id, name=user.name, phone=str(user.phone), role=user.role)


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
    owner_telegram_chat_id: str | None

    @classmethod
    def from_entity(cls, tenant: Tenant) -> "TenantResponse":
        return cls(
            id=tenant.id, name=tenant.name,
            owner_telegram_chat_id=tenant.owner_telegram_chat_id,
        )
