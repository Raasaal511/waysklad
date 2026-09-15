from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork


class GetProductHistoryUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, product_id: int) -> list[AuditEntry]:
        async with self._uow as uow:
            return await uow.audit.list_by_entity("product", product_id)
