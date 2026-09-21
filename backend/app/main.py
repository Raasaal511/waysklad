import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.staticfiles import StaticFiles

from app import router as main_router
from app.infrastructure.config import settings
from app.infrastructure.files import UPLOAD_DIR
from app.infrastructure.observability.logging import configure_logging, get_logger
from app.infrastructure.rate_limit import limiter
from app.infrastructure.notifications.ws_broadcast import broadcaster
from app.presentation.deps.cache import CacheDep
from app.presentation.deps.session import SessionFactoryDep
from app.presentation.errors import register_exception_handlers

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await broadcaster.start()
    yield
    await broadcaster.stop()

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

# Свой фронт всегда на том же origin (прод — nginx проксирует /api на тот же
# домен, dev — Vite proxy), поэтому дефолт "не подключать CORS вовсе"
# безопаснее и проще, чем добавлять "*" — без явного whitelist в .env браузер
# просто блокирует межсайтовые fetch, как и должно быть.
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(main_router)
register_exception_handlers(app)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


_health_logger = get_logger("app.health")
_HEALTH_TIMEOUT_SECONDS = 3.0


async def _check_db(session_factory) -> bool:
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        _health_logger.exception("Health-check: БД недоступна")
        return False


async def _check_cache(cache) -> bool:
    try:
        return await cache.ping()
    except Exception:
        _health_logger.exception("Health-check: Redis (кеш) недоступен")
        return False


@app.get("/api/health")
async def health(response: Response, session_factory: SessionFactoryDep, cache: CacheDep) -> dict:
    """Раньше был всегда {"status": "ok"} без единой реальной проверки —
    контейнер мог быть "up" и проходить healthcheck, даже если БД или Redis
    отвалились (например, после рестарта соседнего контейнера) — никто не
    узнал бы, кроме зависшего пользователя. Таймаут — чтобы сам health-check
    не подвисал на недоступной БД дольше, чем нужно docker compose. Через
    Depends (не settings/engine напрямую), чтобы тесты могли подменить БД/кеш
    так же, как остальные эндпоинты — см. dependency_overrides в conftest.py."""
    try:
        db_ok, cache_ok = await asyncio.wait_for(
            asyncio.gather(_check_db(session_factory), _check_cache(cache)),
            timeout=_HEALTH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        _health_logger.error("Health-check: проверка БД/Redis не уложилась в %.0fс", _HEALTH_TIMEOUT_SECONDS)
        db_ok = cache_ok = False
    if not (db_ok and cache_ok):
        response.status_code = 503
    return {"status": "ok" if db_ok and cache_ok else "degraded", "db": db_ok, "cache": cache_ok}
