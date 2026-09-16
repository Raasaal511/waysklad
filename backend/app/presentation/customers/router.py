from fastapi import APIRouter, Request

from app.application.customers.get_login_status import GetCustomerLoginStatusCommand
from app.application.customers.request_login_link import RequestCustomerLoginLinkCommand
from app.infrastructure.rate_limit import limiter
from app.presentation.customers.schemas import (
    CustomerLoginStatusResponse,
    CustomerProfileResponse,
    CustomerResponse,
    RequestCustomerLoginLinkRequest,
    RequestCustomerLoginLinkResponse,
    UpdateCustomerProfileRequest,
)
from app.presentation.deps import (
    GetCustomerLoginStatusDep,
    GetCustomerProfileDep,
    RequestCustomerLoginLinkDep,
    UpdateCustomerProfileDep,
)
from app.presentation.deps.customer_auth import CurrentCustomerDep

router = APIRouter(prefix="/auth/customer", tags=["customer-auth"])


@router.post("/login-link")
@limiter.limit("10/hour")
async def request_customer_login_link(
    request: Request,
    body: RequestCustomerLoginLinkRequest,
    use_case: RequestCustomerLoginLinkDep,
) -> RequestCustomerLoginLinkResponse:
    result = await use_case.execute(RequestCustomerLoginLinkCommand(body.phone))
    return RequestCustomerLoginLinkResponse.from_result(result)


@router.get("/login-status")
async def get_customer_login_status(
    token: str, use_case: GetCustomerLoginStatusDep
) -> CustomerLoginStatusResponse:
    result = await use_case.execute(GetCustomerLoginStatusCommand(token))
    return CustomerLoginStatusResponse.from_result(result)


@router.get("/me")
async def get_customer_profile(
    customer: CurrentCustomerDep, use_case: GetCustomerProfileDep
) -> CustomerProfileResponse:
    result = await use_case.execute(customer.id)
    return CustomerProfileResponse.from_result(result)


@router.put("/me")
async def update_customer_profile(
    body: UpdateCustomerProfileRequest,
    customer: CurrentCustomerDep,
    use_case: UpdateCustomerProfileDep,
) -> CustomerResponse:
    updated = await use_case.execute(body.to_command(customer.id))
    return CustomerResponse.from_entity(updated)
