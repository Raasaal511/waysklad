from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin


class DebtModel(Base, TenantMixin, TimestampMixin):
    """Запись долговой книги: «запиши на меня» (клиент) либо «взяли под долг» (поставщик)."""

    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint(
            "(client_id IS NOT NULL) != (supplier_id IS NOT NULL)",
            name="ck_debts_one_counterparty",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"))  # долг из продажи
    receipt_document_id: Mapped[int | None] = mapped_column(ForeignKey("stock_documents.id"))  # долг из приёмки
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    issued_at: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)  # «обещал вернуть до…», для напоминаний
    note: Mapped[str] = mapped_column(Text, default="")

    repayments: Mapped[list["DebtRepaymentModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    installments: Mapped[list["DebtInstallmentModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    extensions: Mapped[list["DebtExtensionModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class DebtRepaymentModel(Base, TenantMixin):
    __tablename__ = "debt_repayments"

    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class DebtInstallmentModel(Base, TenantMixin):
    """Платёж графика беспроцентной рассрочки."""

    __tablename__ = "debt_installments"

    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"))
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class DebtExtensionModel(Base, TenantMixin):
    """История переносов срока долга («продлить долг»)."""

    __tablename__ = "debt_extensions"

    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"))
    old_due_date: Mapped[date | None] = mapped_column(Date)
    new_due_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[date] = mapped_column(Date)
