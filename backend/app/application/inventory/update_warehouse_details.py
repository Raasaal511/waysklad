from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Warehouse
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class UpdateWarehouseDetailsCommand:
    warehouse_id: int
    name: str
    address: str = ""


class UpdateWarehouseDetailsUseCase:
    """Владелец/управляющий меняет название и адрес склада."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: UpdateWarehouseDetailsCommand) -> Warehouse:
        require(actor, Permission.WAREHOUSES_MANAGE)

        async with self._uow as uow:
            warehouse = await uow.warehouses.update_details(
                cmd.warehouse_id, cmd.name, cmd.address
            )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "warehouse.update_details", warehouse.id,
                    name=warehouse.name, address=warehouse.address,
                )
            )
            await uow.commit()
            return warehouse
