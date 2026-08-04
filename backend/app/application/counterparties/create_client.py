from dataclasses import dataclass
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.money import Money
from app.domain.common.phone import Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Client
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class CreateClientCommand:
    name: str
    phone: str = ""
    whatsapp: str = ""
    city: str = ""
    debt_limit: Decimal | None = None


class CreateClientUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateClientCommand) -> Client:
        require(actor, Permission.CLIENTS_MANAGE)

        async with self._uow as uow:
            client = await uow.clients.add(
                Client(
                    id=None,
                    name=cmd.name,
                    phone=Phone(cmd.phone) if cmd.phone else None,
                    whatsapp=Phone(cmd.whatsapp) if cmd.whatsapp else None,
                    city=cmd.city,
                    debt_limit=Money.of(cmd.debt_limit) if cmd.debt_limit is not None else None,
                )
            )
            await uow.audit.add(
                AuditEntry.record(actor, "client.create", client.id, name=client.name)
            )
            await uow.commit()
            return client
