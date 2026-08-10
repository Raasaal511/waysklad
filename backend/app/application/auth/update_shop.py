from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Tenant
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class UpdateShopCommand:
    name: str


class UpdateShopUseCase:
    """Владелец меняет название магазина."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: UpdateShopCommand) -> Tenant:
        require(actor, Permission.SETTINGS_MANAGE)
        if not cmd.name.strip():
            raise DomainError("Название магазина не может быть пустым")

        async with self._uow as uow:
            tenant = await uow.tenants.get(uow.tenant_id)
            tenant.name = cmd.name.strip()
            tenant = await uow.tenants.save(tenant)
            await uow.audit.add(AuditEntry.record(actor, "shop.update", tenant.id))
            await uow.commit()
            return tenant
