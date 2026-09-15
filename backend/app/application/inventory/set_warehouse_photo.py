from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.ports import IFileStorage
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Warehouse
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class SetWarehousePhotoCommand:
    warehouse_id: int
    filename: str
    content: bytes


class SetWarehousePhotoUseCase:
    """Логотип склада — необязательный, тот же паттерн что SetProductPhotoUseCase."""

    def __init__(self, uow: IUnitOfWork, storage: IFileStorage):
        self._uow = uow
        self._storage = storage

    async def execute(self, actor: Actor, cmd: SetWarehousePhotoCommand) -> Warehouse:
        require(actor, Permission.WAREHOUSES_MANAGE)

        async with self._uow as uow:
            old_warehouse = await uow.warehouses.get(cmd.warehouse_id)
            old_photo = old_warehouse.photo
            photo = self._storage.save(cmd.filename, cmd.content)
            warehouse = await uow.warehouses.set_photo(cmd.warehouse_id, photo)
            if old_photo:
                self._storage.delete(old_photo)
            await uow.audit.add(
                AuditEntry.record(actor, "warehouse.set_photo", warehouse.id, photo=photo)
            )
            await uow.commit()
            return warehouse
