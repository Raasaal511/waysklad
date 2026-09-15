from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.security import decode_customer_access_token
from app.presentation.deps.session import SessionFactoryDep

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentCustomer:
    id: int


async def get_current_customer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    factory: SessionFactoryDep,
) -> CurrentCustomer:
    """Покупатель витрины — отдельный JWT (scope=customer), не связанный с
    обычными User/Role/tenant (см. security.create_customer_access_token)."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    try:
        payload = decode_customer_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный токен")

    customer_id = int(payload["sub"])
    token_version = payload.get("tv", 0)
    uow = SqlAlchemyUnitOfWork(None, session_factory=factory)
    async with uow:
        current_version = await uow.customers.get_token_version(customer_id)
    if current_version is None or current_version != token_version:
        raise HTTPException(status_code=401, detail="Сессия завершена, войдите снова")
    return CurrentCustomer(id=customer_id)


CurrentCustomerDep = Annotated[CurrentCustomer, Depends(get_current_customer)]
