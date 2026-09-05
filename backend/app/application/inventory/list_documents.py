from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.inventory.entities import StockDocument


class ListDocumentsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[StockDocument]:
        async with self._uow as uow:
            warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
            return await uow.stock_documents.list_all(warehouse_ids)
