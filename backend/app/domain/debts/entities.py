from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import Enum

from app.domain.common.exceptions import DomainError, OverRepaymentError
from app.domain.common.money import Money

SOON_DUE_WINDOW = timedelta(days=3)


class DebtStatus(str, Enum):
    CLOSED = "closed"  # погашен полностью
    PARTIALLY_PAID = "partially_paid"  # погашен частично, ещё есть остаток
    OVERDUE = "overdue"  # срок прошёл, остаток есть
    DUE_SOON = "due_soon"  # срок в ближайшие SOON_DUE_WINDOW дней
    ACTIVE = "active"  # ничего не погашено, срок ещё не подошёл


@dataclass(frozen=True)
class Repayment:
    amount: Money
    on: date
    note: str = ""
    author_id: int | None = None


@dataclass(frozen=True)
class InstallmentPayment:
    """Платёж графика беспроцентной рассрочки."""

    due_date: date
    amount: Money


@dataclass(frozen=True)
class DebtExtension:
    """Запись о переносе срока долга — история продлений."""

    old_due_date: date | None
    new_due_date: date
    reason: str
    author_id: int | None
    created_at: date


@dataclass
class Debt:
    """Запись долговой книги: «запиши на меня» (клиент) либо «взяли под долг» (поставщик).

    Ровно один из client_id/supplier_id — кому мы должны или кто должен нам.
    """

    id: int | None
    amount: Money
    issued_at: date
    warehouse_id: int
    client_id: int | None = None
    supplier_id: int | None = None
    due_date: date | None = None  # «обещал вернуть до…»
    sale_id: int | None = None
    receipt_document_id: int | None = None  # долг поставщику из приёмки товара
    note: str = ""
    schedule: list[InstallmentPayment] = field(default_factory=list)
    repayments: list[Repayment] = field(default_factory=list)
    extensions: list[DebtExtension] = field(default_factory=list)

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

    @property
    def next_installment_due_date(self) -> date | None:
        """Срок ближайшего неоплаченного платежа графика рассрочки.

        Оплаты покрывают платежи графика по порядку (та же эвристика, что и во
        фронтенде — прямой связи Repayment→InstallmentPayment в данных нет).
        None, если графика нет или все его платежи уже покрыты оплатами.
        """
        paid_so_far = self.repaid
        for installment in self.schedule:
            if paid_so_far >= installment.amount:
                paid_so_far = paid_so_far - installment.amount
                continue
            return installment.due_date
        return None

    def status(self, today: date | None = None) -> DebtStatus:
        today = today or date.today()
        if self.is_closed:
            return DebtStatus.CLOSED
        effective_due_date = self.next_installment_due_date or self.due_date
        if effective_due_date is not None and effective_due_date < today:
            return DebtStatus.OVERDUE
        if self.repaid > Money.zero():
            return DebtStatus.PARTIALLY_PAID
        if effective_due_date is not None and effective_due_date - today <= SOON_DUE_WINDOW:
            return DebtStatus.DUE_SOON
        return DebtStatus.ACTIVE

    def repay(self, amount: Money, on: date, note: str = "", author_id: int | None = None) -> None:
        if not amount > Money.zero():
            raise DomainError("Сумма погашения должна быть больше нуля")
        if amount > self.balance:
            raise OverRepaymentError("Погашение больше остатка долга")
        self.repayments.append(Repayment(amount, on, note=note, author_id=author_id))

    def extend(self, new_due_date: date, reason: str, author_id: int | None, today: date | None = None) -> None:
        today = today or date.today()
        if new_due_date < today:
            raise DomainError("Новый срок долга не может быть в прошлом")
        self.extensions.append(
            DebtExtension(
                old_due_date=self.due_date,
                new_due_date=new_due_date,
                reason=reason,
                author_id=author_id,
                created_at=today,
            )
        )
        self.due_date = new_due_date


def total_balance(debts: list[Debt]) -> Money:
    total = Money.zero()
    for debt in debts:
        total = total + debt.balance
    return total


def snapshot_as_of(debts: list[Debt], as_of: date) -> list[Debt]:
    """Срез долгов на дату сверки: долги, выданные позже as_of, не показываем;
    у остальных считаем repaid/balance/status только по погашениям и продлениям
    до as_of включительно — repaid/balance пересчитаются сами (вычисляемые
    property от self.repayments)."""
    result = []
    for debt in debts:
        if debt.issued_at > as_of:
            continue
        result.append(
            replace(
                debt,
                repayments=[r for r in debt.repayments if r.on <= as_of],
                extensions=[e for e in debt.extensions if e.created_at <= as_of],
            )
        )
    return result
