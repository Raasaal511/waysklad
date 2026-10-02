from fastapi import APIRouter, Request

from app.application.customers.get_login_status import GetCustomerLoginStatusCommand
from app.application.customers.login_with_password import LoginCustomerCommand
from app.application.customers.register_with_password import RegisterCustomerCommand
from app.application.customers.change_password import ChangeCustomerPasswordCommand
from app.application.customers.request_login_link import RequestCustomerLoginLinkCommand
from app.infrastructure.rate_limit import limiter
from app.presentation.customers.schemas import (
    CustomerAuthResponse,
    CustomerLoginStatusResponse,
    CustomerProfileResponse,
    CustomerResponse,
    LoginCustomerRequest,
    ChangeCustomerPasswordRequest,
    CustomerChatMessageResponse,
    CustomerChatSummaryResponse,
    CustomerTokenResponse,
    SendCustomerChatMessageRequest,
    RegisterCustomerRequest,
    RegisterCustomerResponse,
    RequestCustomerLoginLinkRequest,
    RequestCustomerLoginLinkResponse,
    UpdateCustomerProfileRequest,
)
from app.presentation.deps import (
    GetCustomerLoginStatusDep,
    LoginCustomerDep,
    RegisterCustomerDep,
    ChangeCustomerPasswordDep,
    ListCustomerChatMessagesDep,
    ListCustomerChatsDep,
    SendCustomerChatMessageDep,
    LogoutAllCustomerDep,
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
            personal_data_consent=body.personal_data_consent,
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


@router.patch("/me/password")
async def change_customer_password(
    body: ChangeCustomerPasswordRequest,
    customer: CurrentCustomerDep,
    use_case: ChangeCustomerPasswordDep,
) -> CustomerTokenResponse:
    result = await use_case.execute(
        ChangeCustomerPasswordCommand(
            customer_id=customer.id,
            new_password=body.new_password,
            current_password=body.current_password,
        )
    )
    return CustomerTokenResponse(access_token=result.access_token)


@router.post("/me/logout-all", status_code=204)
async def logout_all_customer(
    customer: CurrentCustomerDep, use_case: LogoutAllCustomerDep
) -> None:
    """Выйти на всех устройствах — включая то, с которого вызван запрос."""
    await use_case.execute(customer.id)


@router.get("/chats")
async def list_customer_chats(
    customer: CurrentCustomerDep, use_case: ListCustomerChatsDep
) -> list[CustomerChatSummaryResponse]:
    """Диалоги по всем заказам покупателя — вкладка «Чаты» в профиле."""
    summaries = await use_case.execute(customer.id)
    return [CustomerChatSummaryResponse.from_summary(s) for s in summaries]


@router.get("/chats/{request_id}")
async def list_customer_chat_messages(
    request_id: int, customer: CurrentCustomerDep, use_case: ListCustomerChatMessagesDep
) -> list[CustomerChatMessageResponse]:
    messages = await use_case.execute(customer.id, request_id)
    return [CustomerChatMessageResponse.from_entity(m) for m in messages]


@router.post("/chats/{request_id}", status_code=201)
@limiter.limit("120/minute")
async def send_customer_chat_message(
    request: Request,
    request_id: int,
    body: SendCustomerChatMessageRequest,
    customer: CurrentCustomerDep,
    use_case: SendCustomerChatMessageDep,
) -> CustomerChatMessageResponse:
    message = await use_case.execute(customer.id, request_id, body.text)
    return CustomerChatMessageResponse.from_entity(message)
