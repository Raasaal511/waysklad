from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.staticfiles import StaticFiles

from app import router as main_router
from app.infrastructure.config import settings
from app.infrastructure.files import UPLOAD_DIR
from app.infrastructure.observability.logging import configure_logging
from app.infrastructure.rate_limit import limiter
from app.infrastructure.notifications.ws_broadcast import broadcaster
from app.presentation.errors import register_exception_handlers

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await broadcaster.start()
    yield
    await broadcaster.stop()

# Дефолтный SECRET_KEY в проде = любой может подделать JWT с любым tenant_id/ролью.
# debug=True допускается только локально, где .env обычно не переопределяет секрет.
if not settings.debug and settings.secret_key == "dev-secret-change-me":
    raise RuntimeError(
        "SECRET_KEY не переопределён — задайте случайный секрет в .env перед запуском в проде"
    )

# /docs, /redoc, /openapi.json раскрывают всю карту API анонимному пользователю —
# оставляем только при debug=True (локальная разработка)
_docs_kwargs = (
    {}
    if settings.debug
    else {"docs_url": None, "redoc_url": None, "openapi_url": None}
)

app = FastAPI(title="ВайСклад API", version="0.1.0", lifespan=lifespan, **_docs_kwargs)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(main_router)
register_exception_handlers(app)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
