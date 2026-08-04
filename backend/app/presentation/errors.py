from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.common.exceptions import (
    AccessDeniedError,
    DomainError,
    NotFoundError,
)


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
