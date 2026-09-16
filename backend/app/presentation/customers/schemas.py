from pydantic import BaseModel, Field

from app.application.customers.get_login_status import CustomerLoginStatusResult
from app.application.customers.get_profile import CustomerProfileResult
from app.application.customers.request_login_link import RequestCustomerLoginLinkResult
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
