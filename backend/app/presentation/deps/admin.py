from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.common.error_log import IErrorLog
from app.infrastructure.observability.admin_alerts import error_log
from app.infrastructure.security import decode_admin_access_token

_bearer = HTTPBearer(auto_error=False)


def require_admin_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """Доступ к /api/admin/* — отдельный JWT (POST /api/admin/login), не связанный
    с обычными User/Role: эти данные (статус сервера, список магазинов, лог
    ошибок) про всю платформу, а не про конкретный tenant."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    try:
        decode_admin_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недействительный токен")


def get_error_log() -> IErrorLog | None:
    # тот же инстанс, что пишет report_unhandled_error — одно Redis-соединение
    # на процесс вместо двух независимых
    return error_log


ErrorLogDep = Annotated[IErrorLog | None, Depends(get_error_log)]
