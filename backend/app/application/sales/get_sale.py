from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, require_warehouse
from app.domain.sales.entities import Sale


class GetSaleUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, sale_id: int) -> Sale:
        async with self._uow as uow:
            sale = await uow.sales.get(sale_id)
            require_warehouse(actor, sale.warehouse_id)
            return sale
