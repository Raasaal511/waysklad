from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.entities import Product
from app.domain.catalog.ports import IFileStorage
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class SetVariantPhotoCommand:
    product_id: int
    variant_id: int
    filename: str
    content: bytes


class SetVariantPhotoUseCase:
    def __init__(self, uow: IUnitOfWork, storage: IFileStorage, cache: ICache | None = None):
        self._uow = uow
        self._storage = storage
        self._cache = cache

    async def execute(self, actor: Actor, cmd: SetVariantPhotoCommand) -> Product:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            product = await uow.products.get(cmd.product_id)
            variant = next((v for v in product.variants if v.id == cmd.variant_id), None)
            if variant is None:
                raise DomainError(f"Вариант {cmd.variant_id} не найден у товара {cmd.product_id}")
            old_photo = variant.photo
            variant.photo = self._storage.save(cmd.filename, cmd.content)
            await uow.products.save(product)
            if old_photo:
                self._storage.delete(old_photo)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "product.set_variant_photo", product.id,
                    variant_id=variant.id, photo=variant.photo,
                )
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return product
