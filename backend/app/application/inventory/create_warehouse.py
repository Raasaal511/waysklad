from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Warehouse
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class CreateWarehouseCommand:
    name: str
    address: str = ""


class CreateWarehouseUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateWarehouseCommand) -> Warehouse:
        require(actor, Permission.WAREHOUSES_MANAGE)

        async with self._uow as uow:
            warehouse = await uow.warehouses.add(
                Warehouse(id=None, name=cmd.name, address=cmd.address)
            )
            await uow.audit.add(
                AuditEntry.record(actor, "warehouse.create", warehouse.id, name=warehouse.name)
            )
            await uow.commit()
            return warehouse
