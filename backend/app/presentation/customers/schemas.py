from datetime import datetime

from pydantic import BaseModel, Field

from app.application.customers.get_login_status import CustomerLoginStatusResult
from app.application.customers.get_profile import CustomerProfileResult
from app.application.customers.login_with_password import LoginCustomerResult
from app.application.customers.change_phone import RequestCustomerPhoneChangeResult
from app.application.customers.request_login_link import RequestCustomerLoginLinkResult
from app.application.customers.register_with_password import RegisterCustomerResult
from app.application.customers.update_profile import UpdateCustomerProfileCommand
from app.application.customers.my_chats import CustomerChatSummary
from app.domain.customers.entities import Customer
from app.domain.storefront.entities import StorefrontMessage


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


class RequestCustomerPhoneChangeRequest(BaseModel):
    new_phone: str


class RequestCustomerPhoneChangeResponse(BaseModel):
    """Та же пара полей, что и у ссылки входа: фронт одинаково ведёт
    покупателя в бота и ждёт возвращения."""

    token: str
    telegram_deep_link: str

    @classmethod
    def from_result(
        cls, result: RequestCustomerPhoneChangeResult
    ) -> "RequestCustomerPhoneChangeResponse":
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
    """Только имя: телефон приходит из контакта Telegram и руками не меняется."""

    name: str = Field(min_length=1, max_length=200)

    model_config = {"extra": "forbid"}

    def to_command(self, customer_id: int) -> UpdateCustomerProfileCommand:
        return UpdateCustomerProfileCommand(customer_id=customer_id, name=self.name)


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
    personal_data_consent: bool = False


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


class ChangeCustomerPasswordRequest(BaseModel):
    """current_password не нужен, если пароля ещё нет (аккаунт из Telegram)."""

    new_password: str = Field(min_length=1, max_length=128)
    current_password: str | None = None


class CustomerTokenResponse(BaseModel):
    """Свежий токен после смены пароля: token_version инкрементируется, и без
    нового токена покупатель разлогинил бы сам себя этим же запросом."""

    access_token: str


class CustomerChatSummaryResponse(BaseModel):
    """Строка вкладки «Чаты»: заявка и превью последнего сообщения."""

    request_id: int
    shop_name: str
    shop_slug: str
    shop_logo: str
    request_status: str
    last_message: str
    last_message_at: datetime | None
    last_message_from_shop: bool
    messages_count: int

    @classmethod
    def from_summary(cls, summary: CustomerChatSummary) -> "CustomerChatSummaryResponse":
        return cls(
            request_id=summary.request_id,
            shop_name=summary.shop_name,
            shop_slug=summary.shop_slug,
            shop_logo=summary.shop_logo,
            request_status=summary.request_status,
            last_message=summary.last_message,
            last_message_at=summary.last_message_at,
            last_message_from_shop=summary.last_message_from_shop,
            messages_count=summary.messages_count,
        )


class CustomerChatMessageResponse(BaseModel):
    id: int | None
    request_id: int
    author: str
    text: str
    created_at: datetime | None

    @classmethod
    def from_entity(cls, message: StorefrontMessage) -> "CustomerChatMessageResponse":
        return cls(
            id=message.id,
            request_id=message.request_id,
            author=message.author.value,
            text=message.text,
            created_at=message.created_at,
        )


class SendCustomerChatMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
