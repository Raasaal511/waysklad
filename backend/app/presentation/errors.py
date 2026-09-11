from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.domain.common.exceptions import (
    AccessDeniedError,
    DomainError,
    NotFoundError,
)
from app.infrastructure.admin_alerts import report_unhandled_error


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AccessDeniedError)
    async def access_denied(request: Request, exc: AccessDeniedError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        # все остальные нарушения бизнес-правил, включая InsufficientStockError
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # запасной барьер на случай гонки — основные конфликты (например,
        # дублирующийся штрихкод) уже отлавливаются явной проверкой в use case
        return JSONResponse(
            status_code=409, content={"detail": "Нарушение уникальности данных — проверьте вводимые значения"}
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        # последний барьер: баг в коде, обрыв БД и т.п. — то, что не предвидели
        # явные обработчики выше. Раньше такие ошибки тихо превращались в 500
        # без единого следа в логах — на проде о падении продажи/долга/синка
        # никто не узнавал, пока не пожалуется пользователь.
        # BackgroundTasks — отправка в Telegram (блокирующий httpx.post) и запись
        # в Redis происходят уже ПОСЛЕ отправки ответа клиенту, не задерживая его.
        tasks = BackgroundTasks()
        tasks.add_task(report_unhandled_error, request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500, content={"detail": "Внутренняя ошибка сервера"}, background=tasks
        )
