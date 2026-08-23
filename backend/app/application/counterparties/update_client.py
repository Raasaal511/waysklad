"""Сценарий: редактирование данных клиента и его деактивация."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.money import Money
from app.domain.common.phone import Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Client
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class UpdateClientCommand:
    client_id: int
    name: str
    phone: str = ""
    whatsapp: str = ""
    city: str = ""
    debt_limit: Decimal | None = None
    is_active: bool = True


class UpdateClientUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: UpdateClientCommand) -> Client:
        require(actor, Permission.CLIENTS_MANAGE)

        async with self._uow as uow:
            client = await uow.clients.get(cmd.client_id)
            client.name = cmd.name
            client.phone = Phone(cmd.phone) if cmd.phone else None
            client.whatsapp = Phone(cmd.whatsapp) if cmd.whatsapp else None
            client.city = cmd.city
            client.debt_limit = Money.of(cmd.debt_limit) if cmd.debt_limit is not None else None
            client.is_active = cmd.is_active
            client = await uow.clients.save(client)

            await uow.audit.add(
                AuditEntry.record(
                    actor, "client.update", client.id,
                    name=client.name, is_active=client.is_active,
                )
            )
            await uow.commit()
            return client
