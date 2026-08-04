from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Supplier
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class CreateSupplierCommand:
    name: str
    contact: str = ""
    note: str = ""


class CreateSupplierUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateSupplierCommand) -> Supplier:
        require(actor, Permission.SUPPLIERS_MANAGE)

        async with self._uow as uow:
            supplier = await uow.suppliers.add(
                Supplier(id=None, name=cmd.name, contact=cmd.contact, note=cmd.note)
            )
            await uow.audit.add(
                AuditEntry.record(actor, "supplier.create", supplier.id, name=supplier.name)
            )
            await uow.commit()
            return supplier
