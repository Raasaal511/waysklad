from app.domain.common.exceptions import AccessDeniedError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.inventory.entities import StockDocument


class GetDocumentUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, document_id: int) -> StockDocument:
        async with self._uow as uow:
            document = await uow.stock_documents.get(document_id)
            if actor.is_warehouse_scoped:
                document_warehouses = {document.warehouse_id, document.to_warehouse_id}
                if document_warehouses.isdisjoint(actor.warehouse_ids):
                    raise AccessDeniedError("Этот склад вам не назначен")
            return document
