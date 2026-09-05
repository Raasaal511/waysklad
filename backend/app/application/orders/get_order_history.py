from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, require_warehouse


class GetOrderHistoryUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, order_id: int) -> list[AuditEntry]:
        async with self._uow as uow:
            require_warehouse(actor, (await uow.orders.get(order_id)).warehouse_id)
            return await uow.audit.list_by_entity("order", order_id)
