from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.entities import Product
from app.domain.catalog.ports import IFileStorage
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class SetProductPhotoCommand:
    product_id: int
    filename: str
    content: bytes


class SetProductPhotoUseCase:
    def __init__(self, uow: IUnitOfWork, storage: IFileStorage, cache: ICache | None = None):
        self._uow = uow
        self._storage = storage
        self._cache = cache

    async def execute(self, actor: Actor, cmd: SetProductPhotoCommand) -> Product:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            product = await uow.products.get(cmd.product_id)
            old_photo = product.photo
            product.photo = self._storage.save(cmd.filename, cmd.content)
            await uow.products.save(product)
            if old_photo:
                self._storage.delete(old_photo)
            await uow.audit.add(
                AuditEntry.record(actor, "product.set_photo", product.id, photo=product.photo)
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return product
