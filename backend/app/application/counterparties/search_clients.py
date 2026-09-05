from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Client
from app.domain.identity.permissions import Actor


@dataclass(frozen=True)
class SearchClientsCommand:
    query: str = ""
    include_inactive: bool = False


class SearchClientsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: SearchClientsCommand) -> list[Client]:
        async with self._uow as uow:
            warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
            return await uow.clients.search(
                cmd.query, include_inactive=cmd.include_inactive, warehouse_ids=warehouse_ids
            )
