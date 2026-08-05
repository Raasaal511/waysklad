from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Tenant
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class ConnectTelegramCommand:
    chat_id: str


class ConnectTelegramUseCase:
    """Владелец подключает Telegram-чат для ежедневной сводки (send_daily_summaries)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ConnectTelegramCommand) -> Tenant:
        require(actor, Permission.SETTINGS_MANAGE)

        async with self._uow as uow:
            tenant = await uow.tenants.get(uow.tenant_id)
            tenant.owner_telegram_chat_id = cmd.chat_id
            tenant = await uow.tenants.save(tenant)
            await uow.audit.add(
                AuditEntry.record(actor, "shop.connect_telegram", tenant.id)
            )
            await uow.commit()
            return tenant
