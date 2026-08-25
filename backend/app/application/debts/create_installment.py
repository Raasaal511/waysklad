from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt, InstallmentPayment
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class InstallmentInput:
    due_date: date
    amount: Decimal


@dataclass(frozen=True)
class CreateInstallmentCommand:
    debt_id: int
    schedule: list[InstallmentInput]


class CreateInstallmentUseCase:
    """Беспроцентная рассрочка: разбить остаток долга на график платежей."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateInstallmentCommand) -> Debt:
        require(actor, Permission.DEBTS_MANAGE)
        if not cmd.schedule:
            raise DomainError("График рассрочки пуст")

        async with self._uow as uow:
            debt = await uow.debts.get(cmd.debt_id)

            today = date.today()
            for payment in cmd.schedule:
                if payment.due_date < today:
                    raise DomainError("Дата платежа графика не может быть в прошлом")

            total = Money.zero()
            for payment in cmd.schedule:
                total = total + Money.of(payment.amount)
            if total != debt.balance:
                raise DomainError(
                    f"Сумма графика {total} не совпадает с остатком долга {debt.balance}"
                )

            debt.schedule = [
                InstallmentPayment(due_date=p.due_date, amount=Money.of(p.amount))
                for p in sorted(cmd.schedule, key=lambda p: p.due_date)
            ]
            await uow.debts.save(debt)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "debt.installment", debt.id, payments=len(debt.schedule)
                )
            )
            await uow.commit()
            return debt
