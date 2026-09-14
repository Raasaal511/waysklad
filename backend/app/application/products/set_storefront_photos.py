from dataclasses import dataclass, field

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.entities import Product
from app.domain.catalog.ports import IFileStorage
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class SetStorefrontPhotosCommand:
    product_id: int
    photos: list[str] = field(default_factory=list)


class SetStorefrontPhotosUseCase:
    """Заменяет порядок/состав витринной галереи целиком — фронт присылает
    новый список URL после drag-n-drop или удаления одной фотографии. URL,
    выпавшие из нового списка, удаляются с диска; новых URL сюда не добавить
    (для загрузки — AddStorefrontPhotoUseCase), только переставить/убрать
    уже загруженные."""

    def __init__(self, uow: IUnitOfWork, storage: IFileStorage, cache: ICache | None = None):
        self._uow = uow
        self._storage = storage
        self._cache = cache

    async def execute(self, actor: Actor, cmd: SetStorefrontPhotosCommand) -> Product:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            product = await uow.products.get(cmd.product_id)
            current = set(product.storefront_photos)
            unknown = [url for url in cmd.photos if url not in current]
            if unknown:
                raise DomainError("Список фото содержит незагруженные URL")

            removed = [url for url in product.storefront_photos if url not in cmd.photos]
            product.storefront_photos = list(cmd.photos)
            await uow.products.save(product)
            for url in removed:
                self._storage.delete(url)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "product.set_storefront_photos", product.id, count=len(cmd.photos)
                )
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return product
