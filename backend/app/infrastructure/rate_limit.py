from slowapi import Limiter
from slowapi.util import get_remote_address

from app.infrastructure.config import settings

# По IP клиента — nginx проксирует backend (см. frontend/nginx.conf), так что
# ограничение полностью на приложении. Без rate_limit_storage_uri — in-memory:
# ок только для одного uvicorn-процесса (рестарт сбрасывает счётчики — приемлемо).
# В проде backend поднят с несколькими воркерами — там storage_uri указывает на
# Redis, иначе у каждого воркера свой независимый счётчик и реальный лимит
# оказывается в N раз мягче заявленного.
limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
    storage_uri=settings.rate_limit_storage_uri,
)
