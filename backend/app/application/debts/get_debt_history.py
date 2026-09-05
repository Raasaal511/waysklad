from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, require_warehouse


class GetDebtHistoryUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, debt_id: int) -> list[AuditEntry]:
        async with self._uow as uow:
            require_warehouse(actor, (await uow.debts.get(debt_id)).warehouse_id)
            return await uow.audit.list_by_entity("debt", debt_id)
