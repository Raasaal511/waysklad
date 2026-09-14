from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.debts.notify import notify_debt_issued
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.notifier import INotifier
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse


@dataclass(frozen=True)
class IssueSupplierDebtCommand:
    supplier_id: int
    warehouse_id: int
    amount: Decimal
    due_date: date | None = None  # «обещали заплатить до…»
    note: str = ""


class IssueSupplierDebtUseCase:
    """«Взяли товар под долг у поставщика» — деньги, которые должны мы."""

    def __init__(self, uow: IUnitOfWork, notifier: INotifier | None = None):
        self._uow = uow
        self._notifier = notifier

    async def execute(self, actor: Actor, cmd: IssueSupplierDebtCommand) -> Debt:
        require(actor, Permission.DEBTS_MANAGE)
        require_warehouse(actor, cmd.warehouse_id)
        amount = Money.of(cmd.amount)
        if not amount > Money.zero():
            raise DomainError("Сумма долга должна быть больше нуля")

        async with self._uow as uow:
            supplier = await uow.suppliers.get(cmd.supplier_id)
            debt = Debt(
                id=None,
                warehouse_id=cmd.warehouse_id,
                supplier_id=supplier.id,
                amount=amount,
                issued_at=date.today(),
                due_date=cmd.due_date,
                note=cmd.note,
            )
            debt.validate()
            debt = await uow.debts.add(debt)
            await uow.suppliers.link_to_warehouse(supplier.id, cmd.warehouse_id)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "debt.issue_supplier", debt.id,
                    supplier_id=supplier.id, amount=str(amount.amount),
                )
            )
            await notify_debt_issued(uow, self._notifier, debt)
            await uow.commit()
            return debt
