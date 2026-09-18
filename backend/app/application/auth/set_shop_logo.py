from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.ports import IFileStorage
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Tenant
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class SetShopLogoCommand:
    filename: str
    content: bytes


class SetShopLogoUseCase:
    """Логотип магазина — тот же паттерн, что SetProductPhotoUseCase/
    SetWarehousePhotoUseCase (M-B1 п.5). Поле — Tenant.logo (в промпте B2
    названо storefront_logo, но это то же самое существующее поле, отдельного
    поля storefront_logo нет). Симметричный DeleteShopLogoUseCase — B2 п.1."""

    def __init__(self, uow: IUnitOfWork, storage: IFileStorage, cache: ICache | None = None):
        self._uow = uow
        self._storage = storage
        self._cache = cache

    async def execute(self, actor: Actor, cmd: SetShopLogoCommand) -> Tenant:
        require(actor, Permission.SETTINGS_MANAGE)

        async with self._uow as uow:
            tenant = await uow.tenants.get(uow.tenant_id)
            old_logo = tenant.logo
            tenant.logo = self._storage.save(cmd.filename, cmd.content)
            tenant = await uow.tenants.save(tenant)
            if old_logo:
                self._storage.delete(old_logo)
            await uow.audit.add(AuditEntry.record(actor, "shop.set_logo", tenant.id))
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return tenant
