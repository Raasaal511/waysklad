from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class IssueDebtCommand:
    client_id: int
    amount: Decimal
    due_date: date | None = None  # «обещал вернуть до…»
    note: str = ""


class IssueDebtUseCase:
    """«Запиши на меня» — долг без продажи (долг из продажи создаёт CreateSaleUseCase)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: IssueDebtCommand) -> Debt:
        require(actor, Permission.DEBTS_MANAGE)
        amount = Money.of(cmd.amount)
        if not amount > Money.zero():
            raise DomainError("Сумма долга должна быть больше нуля")

        async with self._uow as uow:
            client = await uow.clients.get(cmd.client_id)
            if client.debt_limit is not None:
                balance = amount
                for debt in await uow.debts.list_by_client(client.id):
                    balance = balance + debt.balance
                if balance > client.debt_limit:
                    raise DomainError(
                        f"Превышен лимит долга клиента «{client.name}»: "
                        f"{balance} при лимите {client.debt_limit}"
                    )

            debt = await uow.debts.add(
                Debt(
                    id=None,
                    client_id=cmd.client_id,
                    amount=amount,
                    issued_at=date.today(),
                    due_date=cmd.due_date,
                    note=cmd.note,
                )
            )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "debt.issue", debt.id,
                    client_id=cmd.client_id, amount=str(amount.amount),
                )
            )
            await uow.commit()
            return debt
