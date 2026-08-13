from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.common.exceptions import AccessDeniedError
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor, Permission, has_permission
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.security import decode_access_token
from app.presentation.deps.session import SessionFactoryDep

_bearer = HTTPBearer(auto_error=False)

# роли, чьи данные фильтруются по списку привязанных складов
_WAREHOUSE_SCOPED_ROLES = (Role.MANAGER, Role.SELLER, Role.STOREKEEPER)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    tenant_id: int
    role: Role


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    return CurrentUser(
        id=int(payload["sub"]),
        tenant_id=payload["tenant_id"],
        role=Role(payload["role"]),
    )


async def get_actor(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    factory: SessionFactoryDep,
) -> Actor:
    if user.role not in _WAREHOUSE_SCOPED_ROLES:
        return Actor(id=user.id, role=user.role)
    # manager/seller/storekeeper видят только свои склады — подгружаем список назначений
    uow = SqlAlchemyUnitOfWork(user.tenant_id, session_factory=factory)
    async with uow:
        warehouse_ids = [w.id for w in await uow.warehouses.list_for_user(user.id)]
    return Actor(id=user.id, role=user.role, warehouse_ids=warehouse_ids)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
ActorDep = Annotated[Actor, Depends(get_actor)]


def require_permission(permission: Permission) -> Depends:
    """Проверка права на уровне роутера: APIRouter(dependencies=[require_permission(...)])."""

    def checker(user: CurrentUserDep) -> None:
        if not has_permission(user.role, permission):
            raise AccessDeniedError(f"Роль «{user.role}» не имеет права «{permission}»")

    return Depends(checker)


def get_show_purchase(user: CurrentUserDep) -> bool:
    return has_permission(user.role, Permission.PURCHASE_PRICES_VIEW)


ShowPurchaseDep = Annotated[bool, Depends(get_show_purchase)]
