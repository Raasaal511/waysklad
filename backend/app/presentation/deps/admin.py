import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.domain.common.error_log import IErrorLog
from app.infrastructure.admin_alerts import error_log
from app.infrastructure.config import settings


def require_admin_token(x_admin_token: str = Header(default="")) -> None:
    """Доступ к /api/admin/* — отдельный секрет, не JWT/Role: эти данные
    (статус сервера, лог ошибок) про всю платформу, а не про tenant, к
    которому привязаны обычные роли (owner/manager/...)."""
    if not settings.admin_api_token or not secrets.compare_digest(
        x_admin_token, settings.admin_api_token
    ):
        raise HTTPException(status_code=403, detail="Доступ запрещён")


def get_error_log() -> IErrorLog | None:
    # тот же инстанс, что пишет report_unhandled_error — одно Redis-соединение
    # на процесс вместо двух независимых
    return error_log


ErrorLogDep = Annotated[IErrorLog | None, Depends(get_error_log)]
