from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor


def _scoped(actor: Actor, debts: list[Debt]) -> list[Debt]:
    """Оставляет только долги складов актора, если он warehouse-scoped."""
    if not actor.is_warehouse_scoped:
        return debts
    allowed = set(actor.warehouse_ids)
    return [d for d in debts if d.warehouse_id in allowed]


class GetDebtsOverviewUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor):
        async with self._uow as uow:
            debts = _scoped(actor, await uow.debts.list_active())
            clients = await uow.clients.search("", include_inactive=True)
            suppliers = await uow.suppliers.list()
            counterparty_name = {("client", c.id): c.name for c in clients}
            counterparty_name.update({("supplier", s.id): s.name for s in suppliers})
            return debts, counterparty_name
