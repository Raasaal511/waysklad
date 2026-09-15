from datetime import date

from app.application.debts.get_debts_overview import _scoped
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt, snapshot_as_of
from app.domain.identity.permissions import Actor


class ListClientDebtsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, client_id: int, on: date | None = None) -> list[Debt]:
        async with self._uow as uow:
            debts = _scoped(actor, await uow.debts.list_by_client(client_id))
            if on is not None:
                debts = snapshot_as_of(debts, on)
            return debts


class ListSupplierDebtsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, supplier_id: int, on: date | None = None) -> list[Debt]:
        async with self._uow as uow:
            debts = _scoped(actor, await uow.debts.list_by_supplier(supplier_id))
            if on is not None:
                debts = snapshot_as_of(debts, on)
            return debts
