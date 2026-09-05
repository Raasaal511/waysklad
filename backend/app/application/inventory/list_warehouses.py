from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Warehouse
from app.domain.identity.permissions import Actor


class ListWarehousesUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[Warehouse]:
        async with self._uow as uow:
            if actor.is_warehouse_scoped:
                return await uow.warehouses.list_for_user(actor.id)
            return await uow.warehouses.list()
