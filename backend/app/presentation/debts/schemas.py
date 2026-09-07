from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.application.debts.create_installment import (
    CreateInstallmentCommand,
    InstallmentInput,
)
from app.application.debts.extend_debt import ExtendDebtCommand
from app.application.debts.issue_debt import IssueDebtCommand
from app.application.debts.issue_supplier_debt import IssueSupplierDebtCommand
from app.application.debts.list_due_debts import DueDebtItem
from app.application.debts.repay_debt import RepayDebtCommand
from app.domain.debts.entities import Debt, DebtStatus, total_balance


class IssueDebtRequest(BaseModel):
    client_id: int
    warehouse_id: int
    amount: Decimal
    due_date: date | None = None
    note: str = ""

    def to_command(self) -> IssueDebtCommand:
        return IssueDebtCommand(
            client_id=self.client_id,
            warehouse_id=self.warehouse_id,
            amount=self.amount,
            due_date=self.due_date,
            note=self.note,
        )


class IssueSupplierDebtRequest(BaseModel):
    supplier_id: int
    warehouse_id: int
    amount: Decimal
    due_date: date | None = None
    note: str = ""

    def to_command(self) -> IssueSupplierDebtCommand:
        return IssueSupplierDebtCommand(
            supplier_id=self.supplier_id,
            warehouse_id=self.warehouse_id,
            amount=self.amount,
            due_date=self.due_date,
            note=self.note,
        )


class RepayDebtRequest(BaseModel):
    amount: Decimal
    paid_on: date | None = None
    note: str = ""

    def to_command(self, debt_id: int) -> RepayDebtCommand:
        return RepayDebtCommand(
            debt_id=debt_id, amount=self.amount, paid_on=self.paid_on, note=self.note,
        )


class DebtsFilterParams(BaseModel):
    """Query-параметры списка долгов — форма запроса; преобразование в raw_params
    для generic filter-системы см. to_raw_params()."""

    limit: int = Field(50, le=50)
    offset: int = Field(0, ge=0)
    order_by: str | None = None
    direction: Literal["client", "supplier"] | None = None
    status: DebtStatus | None = None
    query: str = ""

    model_config = {"extra": "forbid"}

    def to_raw_params(self) -> dict:
        raw: dict = {
            "limit": self.limit,
            "offset": self.offset,
            "order_by": self.order_by,
            "status": self.status,
        }
        if self.direction == "client":
            raw["client_id__is_null"] = False
        elif self.direction == "supplier":
            raw["supplier_id__is_null"] = False
        if self.query.strip():
            raw["counterparty_name__ilike"] = self.query.strip()
        return raw


class ExtendDebtRequest(BaseModel):
    new_due_date: date
    reason: str = ""

    def to_command(self, debt_id: int) -> ExtendDebtCommand:
        return ExtendDebtCommand(
            debt_id=debt_id, new_due_date=self.new_due_date, reason=self.reason,
        )


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


class RepaymentResponse(BaseModel):
    amount: Decimal
    on: date
    note: str
    author_id: int | None


class ExtensionResponse(BaseModel):
    old_due_date: date | None
    new_due_date: date
    reason: str
    author_id: int | None
    created_at: date


class DebtResponse(BaseModel):
    id: int
    warehouse_id: int
    client_id: int | None
    supplier_id: int | None
    amount: Decimal
    repaid: Decimal
    balance: Decimal
    is_closed: bool
    status: str
    issued_at: date
    due_date: date | None
    sale_id: int | None
    receipt_document_id: int | None
    note: str
    schedule: list[InstallmentResponse]
    repayments: list[RepaymentResponse]
    extensions: list[ExtensionResponse]

    @classmethod
    def from_entity(cls, debt: Debt) -> "DebtResponse":
        return cls(
            id=debt.id,
            warehouse_id=debt.warehouse_id,
            client_id=debt.client_id,
            supplier_id=debt.supplier_id,
            amount=debt.amount.amount,
            repaid=debt.repaid.amount,
            balance=debt.balance.amount,
            is_closed=debt.is_closed,
            status=debt.status().value,
            issued_at=debt.issued_at,
            due_date=debt.due_date,
            sale_id=debt.sale_id,
            receipt_document_id=debt.receipt_document_id,
            note=debt.note,
            schedule=[
                InstallmentResponse(due_date=p.due_date, amount=p.amount.amount)
                for p in debt.schedule
            ],
            repayments=[
                RepaymentResponse(
                    amount=r.amount.amount, on=r.on, note=r.note, author_id=r.author_id,
                )
                for r in debt.repayments
            ],
            extensions=[
                ExtensionResponse(
                    old_due_date=e.old_due_date,
                    new_due_date=e.new_due_date,
                    reason=e.reason,
                    author_id=e.author_id,
                    created_at=e.created_at,
                )
                for e in debt.extensions
            ],
        )


class DueDebtResponse(DebtResponse):
    """Просроченный/срочный долг с готовой ссылкой для WhatsApp-напоминания клиенту."""

    whatsapp_reminder_link: str | None

    @classmethod
    def from_item(cls, item: DueDebtItem) -> "DueDebtResponse":
        base = DebtResponse.from_entity(item.debt)
        return cls(**base.model_dump(), whatsapp_reminder_link=item.whatsapp_reminder_link)


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


class UpcomingPaymentResponse(BaseModel):
    debt_id: int
    due_date: date
    amount: Decimal
    counterparty_name: str


class DebtsOverviewResponse(BaseModel):
    """Сводка по всем активным долгам сразу — не зависит от текущих фильтров списка
    (направление/статус/поиск), нужна для виджетов «Нам должны/Мы должны» и
    «ближайшие выплаты» на странице «Долги»."""

    client_total_balance: Decimal
    client_debt_count: int
    supplier_total_balance: Decimal
    supplier_debt_count: int
    upcoming_payments: list[UpcomingPaymentResponse]
    has_scheduled_payments: bool

    @classmethod
    def from_active_debts(
        cls, debts: list[Debt], counterparty_name: dict[tuple[str, int], str],
    ) -> "DebtsOverviewResponse":
        client_debts = [d for d in debts if d.client_id is not None]
        supplier_debts = [d for d in debts if d.supplier_id is not None]
        # Просроченные платежи всё ещё нужно показывать (иначе они пропадают из виду),
        # а будущие — только на ближайший месяц, иначе виджет тонет в графике рассрочки
        # на год-два вперёд. has_scheduled_payments не ограничен горизонтом — по нему
        # кнопка "Выплаты" остаётся видимой, даже если следующий платёж дальше месяца.
        horizon = date.today() + timedelta(days=30)
        upcoming: list[UpcomingPaymentResponse] = []
        has_scheduled_payments = False
        for debt in debts:
            if not debt.schedule:
                continue
            key = ("client", debt.client_id) if debt.client_id is not None else ("supplier", debt.supplier_id)
            name = counterparty_name.get(key, "—")
            paid_so_far = debt.repaid
            for installment in debt.schedule:
                if paid_so_far >= installment.amount:
                    paid_so_far = paid_so_far - installment.amount
                    continue
                has_scheduled_payments = True
                if installment.due_date > horizon:
                    continue
                upcoming.append(
                    UpcomingPaymentResponse(
                        debt_id=debt.id,
                        due_date=installment.due_date,
                        amount=installment.amount.amount,
                        counterparty_name=name,
                    )
                )
        upcoming.sort(key=lambda p: p.due_date)
        return cls(
            client_total_balance=total_balance(client_debts).amount,
            client_debt_count=len(client_debts),
            has_scheduled_payments=has_scheduled_payments,
            supplier_total_balance=total_balance(supplier_debts).amount,
            supplier_debt_count=len(supplier_debts),
            upcoming_payments=upcoming,
        )
