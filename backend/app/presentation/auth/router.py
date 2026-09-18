from fastapi import APIRouter, Request, UploadFile

from app.application.auth.set_shop_logo import SetShopLogoCommand
from app.domain.identity.entities import User
from app.domain.identity.permissions import Permission
from app.infrastructure.rate_limit import limiter
from app.infrastructure.security import create_access_token
from app.presentation.auth.schemas import (
    ChangePasswordRequest,
    ConnectTelegramRequest,
    CreateEmployeeRequest,
    LoginRequest,
    RegisterRequest,
    TenantResponse,
    TokenResponse,
    UpdateEmployeeRequest,
    UpdateShopRequest,
    UserResponse,
)
from app.presentation.deps import (
    ActorDep,
    ChangePasswordDep,
    ConnectTelegramDep,
    CreateEmployeeDep,
    GetShopDep,
    ListEmployeesDep,
    LoginDep,
    LogoutAllDep,
    RegisterShopDep,
    SetShopLogoDep,
    UpdateEmployeeDep,
    UpdateShopDep,
)
from app.presentation.deps.auth import require_permission

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User, shop_slug: str | None = None) -> TokenResponse:
    token = create_access_token(user.id, user.tenant_id, user.role.value, user.token_version)
    return TokenResponse(
        access_token=token, user=UserResponse.from_entity(user), shop_slug=shop_slug
    )


@router.post("/register", status_code=201)
@limiter.limit("10/hour")
async def register_shop(
    request: Request, body: RegisterRequest, use_case: RegisterShopDep
) -> TokenResponse:
    result = await use_case.execute(body.to_command())
    return _token_response(result.owner, result.shop_slug)


@router.post("/login")
@limiter.limit("20/minute")
async def login(request: Request, body: LoginRequest, use_case: LoginDep) -> TokenResponse:
    return _token_response(await use_case.execute(body.to_command()))


@router.post("/employees", status_code=201)
async def create_employee(
    body: CreateEmployeeRequest, actor: ActorDep, use_case: CreateEmployeeDep
) -> UserResponse:
    return UserResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/employees", dependencies=[require_permission(Permission.USERS_MANAGE)])
async def list_employees(use_case: ListEmployeesDep) -> list[UserResponse]:
    items = await use_case.execute()
    return [UserResponse.from_entity(item.user, warehouse_ids=item.warehouse_ids) for item in items]


@router.patch("/employees/{employee_id}", dependencies=[require_permission(Permission.USERS_MANAGE)])
async def update_employee(
    employee_id: int, body: UpdateEmployeeRequest, actor: ActorDep, use_case: UpdateEmployeeDep
) -> UserResponse:
    employee = await use_case.execute(actor, body.to_command(employee_id))
    return UserResponse.from_entity(employee)


@router.post("/telegram")
async def connect_telegram(
    body: ConnectTelegramRequest, actor: ActorDep, use_case: ConnectTelegramDep
) -> TenantResponse:
    return TenantResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/shop")
async def get_shop(use_case: GetShopDep) -> TenantResponse:
    return TenantResponse.from_entity(await use_case.execute())


@router.patch("/shop")
async def update_shop(
    body: UpdateShopRequest, actor: ActorDep, use_case: UpdateShopDep
) -> TenantResponse:
    return TenantResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.post("/shop/logo", status_code=201)
async def set_shop_logo(
    actor: ActorDep, file: UploadFile, use_case: SetShopLogoDep
) -> TenantResponse:
    command = SetShopLogoCommand(file.filename or "logo.jpg", await file.read())
    return TenantResponse.from_entity(await use_case.execute(actor, command))


@router.patch("/me/password")
async def change_password(
    body: ChangePasswordRequest, actor: ActorDep, use_case: ChangePasswordDep
) -> TokenResponse:
    # смена пароля инкрементирует token_version — без выдачи свежего токена
    # пользователь сам разлогинил бы себя же текущим запросом
    return _token_response(await use_case.execute(actor, body.to_command()))


@router.post("/me/logout-all", status_code=204)
async def logout_all(actor: ActorDep, use_case: LogoutAllDep) -> None:
    """Разлогинить себя на всех устройствах — включая то, с которого вызван запрос."""
    await use_case.execute(actor)
