from fastapi import APIRouter, Request

from app.application.customers.get_login_status import GetCustomerLoginStatusCommand
from app.application.customers.login_with_password import LoginCustomerCommand
from app.application.customers.register_with_password import RegisterCustomerCommand
from app.application.customers.request_phone_code import RequestPhoneCodeCommand
from app.application.customers.verify_phone_code import VerifyPhoneCodeCommand
from app.application.customers.request_login_link import RequestCustomerLoginLinkCommand
from app.infrastructure.rate_limit import limiter
from app.presentation.customers.schemas import (
    CustomerAuthResponse,
    CustomerLoginStatusResponse,
    CustomerProfileResponse,
    CustomerResponse,
    LoginCustomerRequest,
    PhoneVerifiedResponse,
    RegisterCustomerRequest,
    RegisterCustomerResponse,
    RequestPhoneCodeResponse,
    VerifyPhoneCodeRequest,
    RequestCustomerLoginLinkRequest,
    RequestCustomerLoginLinkResponse,
    UpdateCustomerProfileRequest,
)
from app.presentation.deps import (
    GetCustomerLoginStatusDep,
    LoginCustomerDep,
    RegisterCustomerDep,
    RequestPhoneCodeDep,
    VerifyPhoneCodeDep,
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


@router.post("/register", status_code=201)
@limiter.limit("10/hour")
async def register_customer(
    request: Request, body: RegisterCustomerRequest, use_case: RegisterCustomerDep
) -> RegisterCustomerResponse:
    """Аккаунт здесь ещё не создаётся — сначала номер подтверждается в
    Telegram-боте по выданной ссылке (см. RegisterCustomerUseCase)."""
    result = await use_case.execute(
        RegisterCustomerCommand(
            username=body.username,
            phone=body.phone,
            password=body.password,
            password_confirm=body.password_confirm,
        )
    )
    return RegisterCustomerResponse.from_result(result)


@router.post("/login")
@limiter.limit("20/hour")
async def login_customer(
    request: Request, body: LoginCustomerRequest, use_case: LoginCustomerDep
) -> CustomerAuthResponse:
    result = await use_case.execute(
        LoginCustomerCommand(login=body.login, password=body.password)
    )
    return CustomerAuthResponse.from_result(result)


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


@router.post("/phone/request-code")
@limiter.limit("20/hour")
async def request_phone_code(
    request: Request, customer: CurrentCustomerDep, use_case: RequestPhoneCodeDep
) -> RequestPhoneCodeResponse:
    """Телефон берётся из аккаунта — тело запроса пустое, иначе кодом можно
    было бы засыпать произвольный чужой номер."""
    result = await use_case.execute(RequestPhoneCodeCommand(customer_id=customer.id))
    return RequestPhoneCodeResponse.from_result(result)


@router.post("/phone/verify")
@limiter.limit("30/hour")
async def verify_phone_code(
    request: Request,
    body: VerifyPhoneCodeRequest,
    customer: CurrentCustomerDep,
    use_case: VerifyPhoneCodeDep,
) -> PhoneVerifiedResponse:
    updated = await use_case.execute(
        VerifyPhoneCodeCommand(customer_id=customer.id, code=body.code)
    )
    return PhoneVerifiedResponse(
        phone_verified=updated.phone_verified, phone_verified_at=updated.phone_verified_at
    )
