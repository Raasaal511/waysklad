from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.quantity import Unit
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class CreateUnitCommand:
    code: str
    name: str
    fractional: bool = False


class CreateUnitUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateUnitCommand) -> Unit:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            if await uow.units.get(cmd.code) is not None:
                raise DomainError(f"Единица «{cmd.code}» уже существует")
            unit = Unit(code=cmd.code, name=cmd.name, fractional=cmd.fractional)
            await uow.units.add(unit)
            await uow.audit.add(AuditEntry.record(actor, "unit.create", None, code=unit.code))
            await uow.commit()
        return unit
