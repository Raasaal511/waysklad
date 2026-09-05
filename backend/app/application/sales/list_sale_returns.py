from decimal import Decimal

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, require_warehouse
from app.domain.sales.repository import ISaleReturnRepository


class ListSaleReturnsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, sale_id: int):
        async with self._uow as uow:
            sale = await uow.sales.get(sale_id)
            require_warehouse(actor, sale.warehouse_id)
            price_by_line = {line.id: line.price.amount for line in sale.lines}
            returns = await uow.sale_returns.list_by_sale(sale_id)
            return returns, price_by_line
