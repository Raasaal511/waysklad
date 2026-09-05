from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor, require_warehouse


class GetDebtUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, debt_id: int) -> Debt:
        async with self._uow as uow:
            debt = await uow.debts.get(debt_id)
            require_warehouse(actor, debt.warehouse_id)
            return debt
