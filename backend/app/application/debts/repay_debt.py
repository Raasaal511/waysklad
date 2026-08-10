from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.money import Money
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class RepayDebtCommand:
    debt_id: int
    amount: Decimal
    paid_on: date | None = None  # по умолчанию — сегодня
    note: str = ""


class RepayDebtUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: RepayDebtCommand) -> Debt:
        require(actor, Permission.DEBTS_MANAGE)

        async with self._uow as uow:
            debt = await uow.debts.get(cmd.debt_id)
            debt.repay(
                Money.of(cmd.amount),
                on=cmd.paid_on or date.today(),
                note=cmd.note,
                author_id=actor.id,
            )
            await uow.debts.save(debt)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "debt.repay", debt.id,
                    amount=str(cmd.amount), balance=str(debt.balance.amount),
                )
            )
            await uow.commit()
            return debt
