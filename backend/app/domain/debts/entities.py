from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain.common.exceptions import DomainError, OverRepaymentError
from app.domain.common.money import Money


@dataclass(frozen=True)
class Repayment:
    amount: Money
    on: date


@dataclass(frozen=True)
class InstallmentPayment:
    """Платёж графика беспроцентной рассрочки."""

    due_date: date
    amount: Money


@dataclass
class Debt:
    """Запись долговой книги: «запиши на меня» (клиент) либо «взяли под долг» (поставщик).

    Ровно один из client_id/supplier_id — кому мы должны или кто должен нам.
    """

    id: int | None
    amount: Money
    issued_at: date
    client_id: int | None = None
    supplier_id: int | None = None
    due_date: date | None = None  # «обещал вернуть до…»
    sale_id: int | None = None
    note: str = ""
    schedule: list[InstallmentPayment] = field(default_factory=list)
    repayments: list[Repayment] = field(default_factory=list)

    def validate(self) -> None:
        if (self.client_id is None) == (self.supplier_id is None):
            raise DomainError(
                "Долг должен относиться либо к клиенту, либо к поставщику — не к обоим и не ни к одному"
            )

    @property
    def repaid(self) -> Money:
        total = Money.zero()
        for repayment in self.repayments:
            total = total + repayment.amount
        return total

    @property
    def balance(self) -> Money:
        return self.amount - self.repaid

    @property
    def is_closed(self) -> bool:
        return self.balance == Money.zero()

    def repay(self, amount: Money, on: date) -> None:
        if not amount > Money.zero():
            raise DomainError("Сумма погашения должна быть больше нуля")
        if amount > self.balance:
            raise OverRepaymentError("Погашение больше остатка долга")
        self.repayments.append(Repayment(amount, on))


def total_balance(debts: list[Debt]) -> Money:
    total = Money.zero()
    for debt in debts:
        total = total + debt.balance
    return total
