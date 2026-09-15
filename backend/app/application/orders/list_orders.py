from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.orders.entities import Order


class ListActiveOrdersUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[Order]:
        async with self._uow as uow:
            warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
            return await uow.orders.list_active(warehouse_ids)


class ListCompletedOrdersUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[Order]:
        async with self._uow as uow:
            warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
            return await uow.orders.list_completed(warehouse_ids)
