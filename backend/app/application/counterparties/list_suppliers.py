from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Supplier
from app.domain.identity.permissions import Actor


class ListSuppliersUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[Supplier]:
        async with self._uow as uow:
            warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
            return await uow.suppliers.list(warehouse_ids=warehouse_ids)
