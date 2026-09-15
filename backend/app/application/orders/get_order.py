from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, require_warehouse
from app.domain.orders.entities import Order


class GetOrderUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, order_id: int) -> Order:
        async with self._uow as uow:
            order = await uow.orders.get(order_id)
            require_warehouse(actor, order.warehouse_id)
            return order
