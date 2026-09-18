"""cache-aside для use case'ов с ICache: пробуем прочитать готовый результат,
при промахе — считаем через compute и кешируем. JSON, а не pickle — значения
кладёт use case, а достаёт их RedisCache: десериализация untrusted-байт через
pickle.loads была бы RCE-вектором, если кто-то когда-то подменит содержимое кеша."""

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork

T = TypeVar("T")


def cache_key(namespace: str, *parts: object) -> str:
    raw = "|".join(repr(p) for p in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"{namespace}:{digest}"


def shop_prefix(slug: str) -> str:
    """Общий префикс для всех storefront-ключей одного магазина — по нему
    invalidate_shop_cache() чистит кеш магазина при мутациях (см. shop_cache.py)."""
    return f"shop:{slug}:"


# Префиксы кросс-tenant кешей маркетплейса (без shop_prefix — их ключ не завязан
# на один slug, т.к. одна запись отвечает сразу за много магазинов). Admin-действия,
# которые должны быть видны на маркетплейсе немедленно (verify/unverify, suspend/
# unsuspend), чистят эти namespace целиком, а не ждут TTL (_CACHE_TTL_SECONDS
# в list_products.py/get_product.py).
MARKETPLACE_CATALOG_PREFIX = "marketplace_catalog:"
MARKETPLACE_PRODUCT_PREFIX = "marketplace_product:"
# главная (M-B2): баннеры/секции меняются при verify/unverify/suspend магазина,
# а также при любой мутации баннера в админке (см. platform_banners.py)
MARKETPLACE_HOME_PREFIX = "marketplace_home:"
MARKETPLACE_SHOPS_PREFIX = "marketplace_shops:"
MARKETPLACE_SUGGEST_PREFIX = "marketplace_suggest:"


async def invalidate_marketplace_cache(cache: ICache | None) -> None:
    if cache is None:
        return
    await cache.delete_prefix(MARKETPLACE_CATALOG_PREFIX)
    await cache.delete_prefix(MARKETPLACE_PRODUCT_PREFIX)
    await cache.delete_prefix(MARKETPLACE_HOME_PREFIX)
    await cache.delete_prefix(MARKETPLACE_SHOPS_PREFIX)
    await cache.delete_prefix(MARKETPLACE_SUGGEST_PREFIX)


async def cached(
    cache: ICache,
    key: str,
    ttl_seconds: int,
    compute: Callable[[], Awaitable[T]],
    to_json: Callable[[T], object],
    from_json: Callable[[object], T],
) -> T:
    """compute() может вернуть None (например, «магазин не найден») — такой
    результат намеренно НЕ кешируется: PATCH /api/auth/shop (storefront_enabled)
    должен сразу сделать магазин видимым, а не ждать истечения TTL."""
    raw = await cache.get(key)
    if raw is not None:
        return from_json(json.loads(raw))

    result = await compute()
    if result is not None:
        await cache.set(key, json.dumps(to_json(result)).encode(), ttl_seconds)
    return result


def cached_use_case(
    namespace: str,
    ttl_seconds: int,
    to_json: Callable[[T], object],
    from_json: Callable[[object], T],
    shop_slug: Callable[[object], str] | None = None,
):
    """Декоратор на _execute_uncached(self, cmd) use case'а с self._cache: ICache | None —
    оборачивает его в cache-aside и отдаёт как execute(). При self._cache is None
    считает без кеша, так use case остаётся рабочим и в местах без ICache в DI.

    shop_slug(cmd), если задан, добавляет к ключу префикс shop_prefix(slug) —
    так invalidate_shop_cache() может снести все ключи одного магазина сразу
    (см. shop_cache.py). Команды без привязки к одному магазину (например,
    кросс-tenant marketplace) shop_slug не передают — их кеш живёт только TTL."""

    def decorator(execute_uncached: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def execute(self, cmd: object) -> T:
            if self._cache is None:
                return await execute_uncached(self, cmd)
            prefix = shop_prefix(shop_slug(cmd)) if shop_slug is not None else ""
            key = prefix + cache_key(namespace, cmd)
            return await cached(
                self._cache,
                key,
                ttl_seconds,
                lambda: execute_uncached(self, cmd),
                to_json,
                from_json,
            )

        return execute

    return decorator


async def invalidate_shop_cache(cache: ICache | None, uow: IUnitOfWork) -> None:
    """Вызывать после uow.commit() в любом use case, меняющем данные, которые
    читает storefront-кеш (Tenant.storefront_enabled/name, Warehouse.show_on_storefront,
    Product.*, Category, Stock.quantity) — иначе изменение станет видно покупателю
    только по истечении TTL (_CACHE_TTL_SECONDS в get_catalog.py/get_product.py)."""
    if cache is None or uow.tenant_id is None:
        return
    tenant = await uow.tenants.get(uow.tenant_id)
    if tenant.slug is None:
        return
    await cache.delete_prefix(shop_prefix(tenant.slug))
