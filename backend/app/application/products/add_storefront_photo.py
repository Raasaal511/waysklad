from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.entities import Product
from app.domain.catalog.ports import IFileStorage
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class AddStorefrontPhotoCommand:
    product_id: int
    filename: str
    content: bytes


class AddStorefrontPhotoUseCase:
    """Добавляет одно фото в конец витринной галереи товара — независимо от
    складского Product.photo. Для удаления/перестановки — SetStorefrontPhotosUseCase."""

    def __init__(self, uow: IUnitOfWork, storage: IFileStorage, cache: ICache | None = None):
        self._uow = uow
        self._storage = storage
        self._cache = cache

    async def execute(self, actor: Actor, cmd: AddStorefrontPhotoCommand) -> Product:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            product = await uow.products.get(cmd.product_id)
            url = self._storage.save(cmd.filename, cmd.content)
            product.storefront_photos = [*product.storefront_photos, url]
            await uow.products.save(product)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "product.add_storefront_photo", product.id, photo=url
                )
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return product
