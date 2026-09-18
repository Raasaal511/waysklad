from sqlalchemy import select, update

from app.domain.common.cache import ICache
from app.infrastructure.cache.cache_aside import invalidate_marketplace_cache, shop_prefix
from app.infrastructure.db.models.identity import TenantModel


async def set_tenant_verified(
    session_factory, cache: ICache | None, tenant_id: int, verified: bool
) -> bool:
    """True — применено, False — tenant_id не существует. Проверенный магазин —
    значок доверия на витрине/маркетплейсе, меняется только админом платформы
    (см. промпт M-B1 п.3), владелец сам повлиять не может. Чистит кеш витрины
    магазина и кросс-tenant кеш маркетплейса сразу — значок должен появиться
    без ожидания TTL."""
    async with session_factory() as session:
        row = (
            await session.execute(
                select(TenantModel.id, TenantModel.slug).where(TenantModel.id == tenant_id)
            )
        ).first()
        if row is None:
            return False
        await session.execute(
            update(TenantModel).where(TenantModel.id == tenant_id).values(is_verified=verified)
        )
        await session.commit()

    if cache is not None and row.slug is not None:
        await cache.delete_prefix(shop_prefix(row.slug))
    await invalidate_marketplace_cache(cache)
    return True
