from datetime import datetime

from pydantic import BaseModel, Field

from app.application.customers.get_login_status import CustomerLoginStatusResult
from app.application.customers.get_profile import CustomerProfileResult
from app.application.customers.login_with_password import LoginCustomerResult
from app.application.customers.request_login_link import RequestCustomerLoginLinkResult
from app.application.customers.request_phone_code import RequestPhoneCodeResult
from app.application.customers.register_with_password import RegisterCustomerResult
from app.application.customers.update_profile import UpdateCustomerProfileCommand
from app.domain.customers.entities import Customer


class RequestCustomerLoginLinkRequest(BaseModel):
    phone: str


class RequestCustomerLoginLinkResponse(BaseModel):
    token: str
    telegram_deep_link: str

    @classmethod
    def from_result(
        cls, result: RequestCustomerLoginLinkResult
    ) -> "RequestCustomerLoginLinkResponse":
        return cls(token=result.token, telegram_deep_link=result.telegram_deep_link)


class CustomerLoginStatusResponse(BaseModel):
    confirmed: bool
    access_token: str | None

    @classmethod
    def from_result(cls, result: CustomerLoginStatusResult) -> "CustomerLoginStatusResponse":
        return cls(confirmed=result.confirmed, access_token=result.access_token)


class CustomerProfileStatsResponse(BaseModel):
    requests_total: int
    requests_accepted: int
    requests_rejected: int
    requests_active: int = 0
    shops_count: int = 0


class CustomerProfileResponse(BaseModel):
    id: int
    phone: str
    name: str
    username: str
    phone_verified: bool
    phone_verified_at: datetime | None
    created_at: datetime | None
    has_password: bool
    stats: CustomerProfileStatsResponse

    @classmethod
    def from_result(cls, result: CustomerProfileResult) -> "CustomerProfileResponse":
        customer = result.customer
        return cls(
            id=customer.id,
            phone=str(customer.phone),
            name=customer.name,
            username=customer.username,
            phone_verified=customer.phone_verified,
            phone_verified_at=customer.phone_verified_at,
            created_at=customer.created_at,
            has_password=customer.has_password,
            stats=CustomerProfileStatsResponse(
                requests_total=result.stats.requests_total,
                requests_accepted=result.stats.requests_accepted,
                requests_rejected=result.stats.requests_rejected,
                requests_active=result.stats.requests_active,
                shops_count=result.stats.shops_count,
            ),
        )

class UpdateCustomerProfileRequest(BaseModel):
    """phone необязателен: не передан — номер не трогаем. Смена номера
    сбрасывает phone_verified (подтверждён был старый номер)."""

    name: str = Field(min_length=1, max_length=200)
    phone: str | None = None

    model_config = {"extra": "forbid"}

    def to_command(self, customer_id: int) -> UpdateCustomerProfileCommand:
        return UpdateCustomerProfileCommand(
            customer_id=customer_id, name=self.name, phone=self.phone
        )


class CustomerResponse(BaseModel):
    """Без статистики — ответ на PUT /me, где заявки не пересчитываются."""

    id: int
    phone: str
    name: str
    username: str = ""
    phone_verified: bool = False

    @classmethod
    def from_entity(cls, customer: Customer) -> "CustomerResponse":
        return cls(
            id=customer.id,
            phone=str(customer.phone),
            name=customer.name,
            username=customer.username,
            # после смены телефона сбрасывается — фронт должен увидеть это
            # сразу в ответе, не перезапрашивая профиль
            phone_verified=customer.phone_verified,
        )


class RegisterCustomerRequest(BaseModel):
    username: str
    phone: str
    password: str
    password_confirm: str


class RegisterCustomerResponse(BaseModel):
    """Токена нет: аккаунт создаётся только после подтверждения номера в
    Telegram-боте. Фронт опрашивает /login-status с этим token, как при
    обычном входе."""

    token: str
    telegram_deep_link: str

    @classmethod
    def from_result(cls, result: RegisterCustomerResult) -> "RegisterCustomerResponse":
        return cls(token=result.token, telegram_deep_link=result.telegram_deep_link)


class LoginCustomerRequest(BaseModel):
    """login — username или телефон."""

    login: str
    password: str


class CustomerAuthResponse(BaseModel):
    """Ответ входа по паролю — токен плюс сам покупатель, чтобы фронту не
    делать отдельный GET /me сразу после входа."""

    access_token: str
    customer: CustomerResponse

    @classmethod
    def from_result(cls, result: LoginCustomerResult) -> "CustomerAuthResponse":
        return cls(
            access_token=result.access_token,
            customer=CustomerResponse.from_entity(result.customer),
        )


class RequestPhoneCodeResponse(BaseModel):
    """telegram_deep_link непуст, когда код слать некуда: покупателю сначала
    нужно открыть бота и нажать «Старт»."""

    sent_via: str
    retry_after: int
    telegram_deep_link: str = ""

    @classmethod
    def from_result(cls, result: RequestPhoneCodeResult) -> "RequestPhoneCodeResponse":
        return cls(
            sent_via=result.sent_via,
            retry_after=result.retry_after,
            telegram_deep_link=result.telegram_deep_link,
        )


class VerifyPhoneCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=12)


class PhoneVerifiedResponse(BaseModel):
    phone_verified: bool
    phone_verified_at: datetime | None


class ChangeCustomerPasswordRequest(BaseModel):
    """current_password не нужен, если пароля ещё нет (аккаунт из Telegram)."""

    new_password: str = Field(min_length=1, max_length=128)
    current_password: str | None = None


class CustomerTokenResponse(BaseModel):
    """Свежий токен после смены пароля: token_version инкрементируется, и без
    нового токена покупатель разлогинил бы сам себя этим же запросом."""

    access_token: str
