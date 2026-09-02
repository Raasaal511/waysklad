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


async def _resolve_current_user(token: str, factory: SessionFactoryDep) -> CurrentUser:
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    user_id = int(payload["sub"])
    tenant_id = payload["tenant_id"]
    # token_version отсутствует в токенах, выданных до этой проверки — считаем их
    # версией 0, чтобы не разлогинить всех разом при выкатке
    token_version = payload.get("tv", 0)
    uow = SqlAlchemyUnitOfWork(tenant_id, session_factory=factory)
    async with uow:
        current_version = await uow.users.get_token_version(user_id)
    if current_version is None or current_version != token_version:
        raise HTTPException(status_code=401, detail="Сессия завершена, войдите снова")
    return CurrentUser(
        id=user_id,
        tenant_id=tenant_id,
        role=Role(payload["role"]),
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    factory: SessionFactoryDep,
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    return await _resolve_current_user(credentials.credentials, factory)


async def get_current_user_ws(token: str, factory: SessionFactoryDep) -> CurrentUser:
    """Для WebSocket-хендшейка: браузер не может выставить кастомный заголовок
    Authorization при открытии сокета — токен передаётся query-параметром
    (?token=...). HTTPException(401) FastAPI сам превращает в закрытие
    хендшейка с кодом 403, что и требуется для непройденной авторизации."""
    return await _resolve_current_user(token, factory)


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
