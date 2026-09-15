from dataclasses import dataclass
from datetime import date

from app.application.debts.get_debts_overview import _scoped
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.debts.reminder import build_debt_reminder_link
from app.domain.identity.permissions import Actor


@dataclass(frozen=True)
class DueDebtItem:
    debt: Debt
    whatsapp_reminder_link: str | None  # None, если у клиента нет телефона / долг поставщику


class ListDueDebtsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, on: date | None = None) -> list[DueDebtItem]:
        async with self._uow as uow:
            debts = _scoped(actor, await uow.debts.list_due(on or date.today()))
            items = []
            for debt in debts:
                client = await uow.clients.get(debt.client_id) if debt.client_id else None
                items.append(
                    DueDebtItem(
                        debt=debt,
                        whatsapp_reminder_link=build_debt_reminder_link(debt, client),
                    )
                )
            return items
