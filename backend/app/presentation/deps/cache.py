from typing import Annotated

from fastapi import Depends

from app.domain.common.cache import ICache
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.config import settings

if not settings.cache_redis_url:
    raise RuntimeError(
        "CACHE_REDIS_URL не задан — кеш витрины/маркетплейса требует Redis "
        "во всех окружениях (см. docker-compose.yml/docker-compose.prod.yml)"
    )

_cache: ICache = RedisCache(settings.cache_redis_url)


def get_cache() -> ICache:
    return _cache


CacheDep = Annotated[ICache, Depends(get_cache)]
