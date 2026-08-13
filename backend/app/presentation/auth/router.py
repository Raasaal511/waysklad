from fastapi import APIRouter

from app.domain.identity.entities import User
from app.domain.identity.permissions import Permission
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
    LoginDep,
    RegisterShopDep,
    UowDep,
    UpdateEmployeeDep,
    UpdateShopDep,
)
from app.presentation.deps.auth import require_permission

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


@router.get("/employees", dependencies=[require_permission(Permission.USERS_MANAGE)])
async def list_employees(uow: UowDep) -> list[UserResponse]:
    async with uow:
        employees = await uow.users.list_by_tenant()
        warehouses = await uow.warehouses.list()
        by_user: dict[int, list[int]] = {}
        for warehouse in warehouses:
            for user_id in warehouse.assigned_user_ids:
                by_user.setdefault(user_id, []).append(warehouse.id)
        return [
            UserResponse.from_entity(u, warehouse_ids=by_user.get(u.id, []))
            for u in employees
        ]


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
async def get_shop(uow: UowDep) -> TenantResponse:
    async with uow:
        return TenantResponse.from_entity(await uow.tenants.get(uow.tenant_id))


@router.patch("/shop")
async def update_shop(
    body: UpdateShopRequest, actor: ActorDep, use_case: UpdateShopDep
) -> TenantResponse:
    return TenantResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.patch("/me/password", status_code=204)
async def change_password(
    body: ChangePasswordRequest, actor: ActorDep, use_case: ChangePasswordDep
) -> None:
    await use_case.execute(actor, body.to_command())
