from dataclasses import dataclass
from datetime import date

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class ExtendDebtCommand:
    debt_id: int
    new_due_date: date
    reason: str = ""


class ExtendDebtUseCase:
    """«Продлить долг» — меняет только срок (due_date), отдельно от правки продажи."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ExtendDebtCommand) -> Debt:
        require(actor, Permission.DEBTS_MANAGE)

        async with self._uow as uow:
            debt = await uow.debts.get(cmd.debt_id)
            if debt.is_closed:
                raise DomainError("Долг уже погашен — продлевать нечего")
            old_due_date = debt.due_date
            debt.extend(cmd.new_due_date, reason=cmd.reason, author_id=actor.id)
            await uow.debts.save(debt)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "debt.extend", debt.id,
                    old_due_date=str(old_due_date) if old_due_date else None,
                    new_due_date=str(cmd.new_due_date),
                    reason=cmd.reason,
                )
            )
            await uow.commit()
            return debt
