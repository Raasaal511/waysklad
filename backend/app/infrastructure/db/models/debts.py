from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin


class DebtModel(Base, TenantMixin, TimestampMixin):
    """Запись долговой книги: «запиши на меня»."""

    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"))  # долг из продажи
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


class DebtRepaymentModel(Base, TenantMixin):
    __tablename__ = "debt_repayments"

    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_on: Mapped[date] = mapped_column(Date)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class DebtInstallmentModel(Base, TenantMixin):
    """Платёж графика беспроцентной рассрочки."""

    __tablename__ = "debt_installments"

    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"))
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
