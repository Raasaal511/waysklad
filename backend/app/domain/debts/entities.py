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
    """Запись долговой книги: «запиши на меня»."""

    id: int | None
    client_id: int
    amount: Money
    issued_at: date
    due_date: date | None = None  # «обещал вернуть до…»
    sale_id: int | None = None
    note: str = ""
    schedule: list[InstallmentPayment] = field(default_factory=list)
    repayments: list[Repayment] = field(default_factory=list)

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
