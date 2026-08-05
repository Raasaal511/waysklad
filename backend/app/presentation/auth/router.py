from fastapi import APIRouter

from app.domain.identity.entities import User
from app.infrastructure.security import create_access_token
from app.presentation.auth.schemas import (
    ConnectTelegramRequest,
    CreateEmployeeRequest,
    LoginRequest,
    RegisterRequest,
    TenantResponse,
    TokenResponse,
    UserResponse,
)
from app.presentation.deps import (
    ActorDep,
    ConnectTelegramDep,
    CreateEmployeeDep,
    LoginDep,
    RegisterShopDep,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User, shop_slug: str | None = None) -> TokenResponse:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return TokenResponse(
        access_token=token, user=UserResponse.from_entity(user), shop_slug=shop_slug
    )


@router.post("/register", status_code=201)
async def register_shop(body: RegisterRequest, use_case: RegisterShopDep) -> TokenResponse:
    result = await use_case.execute(body.to_command())
    return _token_response(result.owner, result.shop_slug)


@router.post("/login")
async def login(body: LoginRequest, use_case: LoginDep) -> TokenResponse:
    return _token_response(await use_case.execute(body.to_command()))


@router.post("/employees", status_code=201)
async def create_employee(
    body: CreateEmployeeRequest, actor: ActorDep, use_case: CreateEmployeeDep
) -> UserResponse:
    return UserResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.post("/telegram")
async def connect_telegram(
    body: ConnectTelegramRequest, actor: ActorDep, use_case: ConnectTelegramDep
) -> TenantResponse:
    return TenantResponse.from_entity(await use_case.execute(actor, body.to_command()))
