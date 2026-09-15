from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Warehouse
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class UpdateWarehouseDetailsCommand:
    warehouse_id: int
    name: str
    address: str = ""
    show_on_storefront: bool = False


class UpdateWarehouseDetailsUseCase:
    """Владелец/управляющий меняет название и адрес склада."""

    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: UpdateWarehouseDetailsCommand) -> Warehouse:
        require(actor, Permission.WAREHOUSES_MANAGE)

        async with self._uow as uow:
            warehouse = await uow.warehouses.update_details(
                cmd.warehouse_id, cmd.name, cmd.address, cmd.show_on_storefront
            )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "warehouse.update_details", warehouse.id,
                    name=warehouse.name, address=warehouse.address,
                )
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
            return warehouse
