from pydantic import BaseModel

from app.application.customers.get_login_status import CustomerLoginStatusResult
from app.application.customers.request_login_link import RequestCustomerLoginLinkResult


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
