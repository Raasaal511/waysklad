from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.entities import Product
from app.domain.catalog.ports import IFileStorage
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class SetProductPhotoCommand:
    product_id: int
    filename: str
    content: bytes


class SetProductPhotoUseCase:
    def __init__(self, uow: IUnitOfWork, storage: IFileStorage):
        self._uow = uow
        self._storage = storage

    async def execute(self, actor: Actor, cmd: SetProductPhotoCommand) -> Product:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            product = await uow.products.get(cmd.product_id)
            product.photo = self._storage.save(cmd.filename, cmd.content)
            await uow.products.save(product)
            await uow.audit.add(
                AuditEntry.record(actor, "product.set_photo", product.id, photo=product.photo)
            )
            await uow.commit()
        return product
