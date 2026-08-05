from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.application.debts.create_installment import (
    CreateInstallmentCommand,
    InstallmentInput,
)
from app.application.debts.issue_debt import IssueDebtCommand
from app.application.debts.issue_supplier_debt import IssueSupplierDebtCommand
from app.application.debts.repay_debt import RepayDebtCommand
from app.domain.debts.entities import Debt, total_balance


class IssueDebtRequest(BaseModel):
    client_id: int
    amount: Decimal
    due_date: date | None = None
    note: str = ""

    def to_command(self) -> IssueDebtCommand:
        return IssueDebtCommand(
            client_id=self.client_id,
            amount=self.amount,
            due_date=self.due_date,
            note=self.note,
        )


class IssueSupplierDebtRequest(BaseModel):
    supplier_id: int
    amount: Decimal
    due_date: date | None = None
    note: str = ""

    def to_command(self) -> IssueSupplierDebtCommand:
        return IssueSupplierDebtCommand(
            supplier_id=self.supplier_id,
            amount=self.amount,
            due_date=self.due_date,
            note=self.note,
        )


class RepayDebtRequest(BaseModel):
    amount: Decimal
    paid_on: date | None = None

    def to_command(self, debt_id: int) -> RepayDebtCommand:
        return RepayDebtCommand(debt_id=debt_id, amount=self.amount, paid_on=self.paid_on)


class InstallmentItemRequest(BaseModel):
    due_date: date
    amount: Decimal


class CreateInstallmentRequest(BaseModel):
    schedule: list[InstallmentItemRequest]

    def to_command(self, debt_id: int) -> CreateInstallmentCommand:
        return CreateInstallmentCommand(
            debt_id=debt_id,
            schedule=[
                InstallmentInput(due_date=p.due_date, amount=p.amount)
                for p in self.schedule
            ],
        )


class InstallmentResponse(BaseModel):
    due_date: date
    amount: Decimal


class DebtResponse(BaseModel):
    id: int
    client_id: int | None
    supplier_id: int | None
    amount: Decimal
    repaid: Decimal
    balance: Decimal
    is_closed: bool
    issued_at: date
    due_date: date | None
    sale_id: int | None
    note: str
    schedule: list[InstallmentResponse]

    @classmethod
    def from_entity(cls, debt: Debt) -> "DebtResponse":
        return cls(
            id=debt.id,
            client_id=debt.client_id,
            supplier_id=debt.supplier_id,
            amount=debt.amount.amount,
            repaid=debt.repaid.amount,
            balance=debt.balance.amount,
            is_closed=debt.is_closed,
            issued_at=debt.issued_at,
            due_date=debt.due_date,
            sale_id=debt.sale_id,
            note=debt.note,
            schedule=[
                InstallmentResponse(due_date=p.due_date, amount=p.amount.amount)
                for p in debt.schedule
            ],
        )


class DebtsSummaryResponse(BaseModel):
    """Баланс контрагента: список долгов + сумма остатков — «сверка одной кнопкой»."""

    total_balance: Decimal
    debts: list[DebtResponse]

    @classmethod
    def from_debts(cls, debts: list[Debt]) -> "DebtsSummaryResponse":
        return cls(
            total_balance=total_balance(debts).amount,
            debts=[DebtResponse.from_entity(d) for d in debts],
        )
