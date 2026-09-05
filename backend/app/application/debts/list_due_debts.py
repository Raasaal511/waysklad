from datetime import date

from app.application.debts.get_debts_overview import _scoped
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor


class ListDueDebtsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, on: date | None = None) -> list[Debt]:
        async with self._uow as uow:
            debts = await uow.debts.list_due(on or date.today())
            return _scoped(actor, debts)
