from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.inventory.entities import StockItem


class ListStockUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[StockItem]:
        async with self._uow as uow:
            items = await uow.stock.list_all()
        if not actor.is_warehouse_scoped:
            return items
        allowed_ids = set(actor.warehouse_ids)
        return [item for item in items if item.warehouse_id in allowed_ids]
