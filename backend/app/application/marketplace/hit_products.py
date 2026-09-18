from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.infrastructure.cache.cache_aside import cached

_HIT_CACHE_TTL_SECONDS = 600  # 10 минут — топ-10% пересчитывается пакетно, не на каждый запрос


async def get_hit_product_ids(
    uow: IUnitOfWork, cache: ICache | None, visible_tenant_ids: list[int]
) -> frozenset[int]:
    """Топ-10% товаров платформы по продажам за 30 дней (см.
    IMarketplaceProductRepository.compute_hit_product_ids) — общий для
    списка/карточки/будущей главной (M-B2), кеш общий на весь платформенный
    набор tenant (не зависит от текущих фильтров каталога), поэтому ключ не
    учитывает visible_tenant_ids по значению — только зовётся с одним и тем же
    набором (все магазины с включённой витриной)."""
    if cache is None:
        return await uow.marketplace_products.compute_hit_product_ids(visible_tenant_ids)

    async def compute() -> frozenset[int]:
        return await uow.marketplace_products.compute_hit_product_ids(visible_tenant_ids)

    return await cached(
        cache,
        "marketplace:hit_products",
        _HIT_CACHE_TTL_SECONDS,
        compute,
        to_json=lambda ids: sorted(ids),
        from_json=lambda ids: frozenset(ids),
    )
