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


class CustomerProfileResponse(BaseModel):
    id: int
    phone: str
    name: str
    stats: CustomerProfileStatsResponse

    @classmethod
    def from_result(cls, result: CustomerProfileResult) -> "CustomerProfileResponse":
        customer = result.customer
        return cls(
            id=customer.id,
            phone=str(customer.phone),
            name=customer.name,
            stats=CustomerProfileStatsResponse(
                requests_total=result.stats.requests_total,
                requests_accepted=result.stats.requests_accepted,
                requests_rejected=result.stats.requests_rejected,
            ),
        )

class UpdateCustomerProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    model_config = {"extra": "forbid"}

    def to_command(self, customer_id: int) -> UpdateCustomerProfileCommand:
        return UpdateCustomerProfileCommand(customer_id=customer_id, name=self.name)


class CustomerResponse(BaseModel):
    """Без статистики — ответ на PUT /me, где заявки не пересчитываются."""

    id: int
    phone: str
    name: str

    @classmethod
    def from_entity(cls, customer: Customer) -> "CustomerResponse":
        return cls(id=customer.id, phone=str(customer.phone), name=customer.name)


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
