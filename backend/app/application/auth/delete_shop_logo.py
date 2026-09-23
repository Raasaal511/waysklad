from app.domain.audit.entities import AuditEntry
from app.domain.catalog.ports import IFileStorage
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Tenant
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


class DeleteShopLogoUseCase:
    """Симметрично SetShopLogoUseCase — сброс логотипа магазина в "" и
    удаление файла из хранилища (промпт B2 п.1)."""

    def __init__(self, uow: IUnitOfWork, storage: IFileStorage, cache: ICache | None = None):
        self._uow = uow
        self._storage = storage
        self._cache = cache

    async def execute(self, actor: Actor) -> Tenant:
        require(actor, Permission.SETTINGS_MANAGE)

        async with self._uow as uow:
            tenant = await uow.tenants.get(uow.tenant_id)
            old_logo = tenant.logo
            tenant.logo = ""
            tenant = await uow.tenants.save(tenant)
            if old_logo:
                self._storage.delete(old_logo)
            await uow.audit.add(AuditEntry.record(actor, "shop.delete_logo", tenant.id))
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return tenant
