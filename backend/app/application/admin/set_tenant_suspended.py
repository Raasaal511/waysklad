from sqlalchemy import select, update

from app.domain.common.cache import ICache
from app.infrastructure.cache.cache_aside import invalidate_marketplace_cache, shop_prefix
from app.infrastructure.db.models.identity import TenantModel


async def set_tenant_suspended(
    session_factory, cache: ICache | None, tenant_id: int, suspended: bool
) -> bool:
    """True — применено, False — tenant_id не существует. Инвалидирует
    storefront-кеш сразу (см. invalidate_shop_cache в cache_aside.py) —
    блокировка/разблокировка не должна ждать TTL, чтобы подействовать на витрину.
    Заодно чистит кросс-tenant кеш маркетплейса (список/карточка товара всех
    магазинов) — блокировка должна сразу убрать магазин из общей ленты."""
    async with session_factory() as session:
        row = (
            await session.execute(
                select(TenantModel.id, TenantModel.slug).where(TenantModel.id == tenant_id)
            )
        ).first()
        if row is None:
            return False
        await session.execute(
            update(TenantModel).where(TenantModel.id == tenant_id).values(is_suspended=suspended)
        )
        await session.commit()

    if cache is not None and row.slug is not None:
        await cache.delete_prefix(shop_prefix(row.slug))
    await invalidate_marketplace_cache(cache)
    return True
