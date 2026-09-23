from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.common.exceptions import AccessDeniedError, NotFoundError
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor, Permission, has_permission
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.security import decode_access_token
from app.presentation.deps.session import SessionFactoryDep

_bearer = HTTPBearer(auto_error=False)

# роли, чьи данные фильтруются по списку привязанных складов
_WAREHOUSE_SCOPED_ROLES = (Role.MANAGER, Role.SELLER, Role.STOREKEEPER)

# «был в сети» с точностью до шага: админке хватает минут, а писать в users
# на каждый запрос — лишняя транзакция и блокировка строки
LAST_SEEN_STEP = timedelta(minutes=5)


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
    try:
        async with uow:
            user_session = await uow.users.get_session(user_id)
            tenant = await uow.tenants.get(tenant_id)
            is_valid = (
                user_session is not None
                and user_session.token_version == token_version
                and not tenant.is_suspended
            )
            if is_valid:
                now = datetime.now(timezone.utc)
                seen = user_session.last_seen_at
                if seen is None or now - seen >= LAST_SEEN_STEP:
                    await uow.users.touch_last_seen(user_id, now)
                    await uow.commit()
    except NotFoundError:
        # tenant_id из токена больше не существует (например, дев-БД пересоздана) —
        # это невалидная сессия, а не «ресурс не найден» на уровне API
        raise HTTPException(status_code=401, detail="Сессия недействительна, войдите снова")
    if user_session is None or user_session.token_version != token_version:
        raise HTTPException(status_code=401, detail="Сессия завершена, войдите снова")
    if tenant.is_suspended:
        # блокировка платформой действует немедленно на уже выданные токены —
        # не ждать истечения access_token_expire_minutes (до 30 дней)
        raise HTTPException(status_code=403, detail="Магазин заблокирован")
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
