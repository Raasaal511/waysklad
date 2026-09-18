from dataclasses import dataclass
from datetime import date

from app.domain.common.cache import ICache
from app.domain.common.exceptions import NotFoundError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_DEDUP_TTL_SECONDS = 30 * 60  # 30 минут, промпт B1 п.5


@dataclass(frozen=True)
class RecordProductViewCommand:
    slug: str
    product_id: int
    client_ip: str


class RecordProductViewUseCase:
    """Засчитать просмотр карточки товара — вызывается публично, без
    авторизации. Дедуплицируется Redis-ключом на (tenant, product, ip):
    повторный просмотр в течение TTL не увеличивает счётчик. Сырые события
    не хранятся — только суточный агрегат в product_view_daily.

    Намеренно НЕ вызывает invalidate_shop_cache: просмотры не должны сносить
    кэш карточки/каталога (см. промпт B1 п.5) — отставание views_90d от
    факта до TTL кэша неприменимо, т.к. GetStorefrontProductUseCase читает
    его отдельным запросом поверх cache-aside (см. get_product.py)."""

    def __init__(self, session_factory, cache: ICache | None):
        self._session_factory = session_factory
        self._cache = cache

    async def execute(self, cmd: RecordProductViewCommand) -> bool:
        """True — просмотр найден и засчитан (или не найден кэш, но товар
        существует и учтён); False — товар не найден/скрыт (вызывающий
        роутер отвечает 404, как у самой карточки)."""
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return False

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            try:
                product = await uow.products.get(cmd.product_id)
            except NotFoundError:
                return False
            if not product.show_on_storefront:
                return False

            if await self._already_counted(tenant.id, product.id, cmd.client_ip):
                return True

            await uow.product_views.record_view(product.id, date.today())
            await uow.commit()

        await self._mark_counted(tenant.id, product.id, cmd.client_ip)
        return True

    def _dedup_key(self, tenant_id: int, product_id: int, client_ip: str) -> str:
        return f"product_view_dedup:{tenant_id}:{product_id}:{client_ip}"

    async def _already_counted(self, tenant_id: int, product_id: int, client_ip: str) -> bool:
        if self._cache is None:
            return False
        key = self._dedup_key(tenant_id, product_id, client_ip)
        return await self._cache.get(key) is not None

    async def _mark_counted(self, tenant_id: int, product_id: int, client_ip: str) -> None:
        if self._cache is None:
            return
        key = self._dedup_key(tenant_id, product_id, client_ip)
        await self._cache.set(key, b"1", _DEDUP_TTL_SECONDS)
