from datetime import date

from sqlalchemy import case, func, select

from app.domain.debts.entities import SOON_DUE_WINDOW, DebtStatus
from app.domain.filtering.operators import Operator
from app.infrastructure.db.filtering.field_spec import DATE_OPS, FieldSpec, NUMERIC_OPS, TEXT_OPS
from app.infrastructure.db.filtering.filter_factory import BaseQueryFilterFactory
from app.infrastructure.db.models.counterparties import ClientModel, SupplierModel
from app.infrastructure.db.models.debts import DebtModel, DebtRepaymentModel


def _repaid_subq():
    return (
        select(func.coalesce(func.sum(DebtRepaymentModel.amount), 0))
        .where(DebtRepaymentModel.debt_id == DebtModel.id)
        .correlate(DebtModel)
        .scalar_subquery()
    )


def _balance_expr():
    return DebtModel.amount - _repaid_subq()


def _status_expr(today: date):
    balance = _balance_expr()
    repaid = _repaid_subq()
    soon_cutoff = today + SOON_DUE_WINDOW
    return case(
        (balance <= 0, DebtStatus.CLOSED.value),
        (DebtModel.due_date < today, DebtStatus.OVERDUE.value),
        (repaid > 0, DebtStatus.PARTIALLY_PAID.value),
        (DebtModel.due_date.is_not(None) & (DebtModel.due_date <= soon_cutoff), DebtStatus.DUE_SOON.value),
        else_=DebtStatus.ACTIVE.value,
    )


def _severity_expr(status_expr):
    return case(
        (status_expr == DebtStatus.OVERDUE.value, 4),
        (status_expr == DebtStatus.DUE_SOON.value, 3),
        (status_expr == DebtStatus.PARTIALLY_PAID.value, 2),
        (status_expr == DebtStatus.ACTIVE.value, 1),
        else_=0,
    )


def _counterparty_name_expr():
    """Имя клиента либо поставщика — ровно один из client_id/supplier_id заполнен."""
    client_name = (
        select(ClientModel.name)
        .where(
            ClientModel.id == DebtModel.client_id,
            ClientModel.tenant_id == DebtModel.tenant_id,
        )
        .correlate(DebtModel)
        .scalar_subquery()
    )
    supplier_name = (
        select(SupplierModel.name)
        .where(
            SupplierModel.id == DebtModel.supplier_id,
            SupplierModel.tenant_id == DebtModel.tenant_id,
        )
        .correlate(DebtModel)
        .scalar_subquery()
    )
    return func.coalesce(client_name, supplier_name)


class DebtFilterFactory(BaseQueryFilterFactory[DebtModel]):
    model = DebtModel
    allowed_order_fields = {"severity", "due_date", "issued_at", "balance"}

    @classmethod
    def build_fields(cls, today: date) -> dict[str, FieldSpec]:
        status_expr = _status_expr(today)
        balance_expr = _balance_expr()
        return {
            "client_id": FieldSpec(DebtModel.client_id, NUMERIC_OPS | {Operator.IS_NULL}),
            "supplier_id": FieldSpec(DebtModel.supplier_id, NUMERIC_OPS | {Operator.IS_NULL}),
            "status": FieldSpec(status_expr, frozenset({Operator.EQ, Operator.IN})),
            "balance": FieldSpec(balance_expr, NUMERIC_OPS),
            "due_date": FieldSpec(DebtModel.due_date, DATE_OPS),
            "issued_at": FieldSpec(DebtModel.issued_at, DATE_OPS),
            "severity": FieldSpec(_severity_expr(status_expr), NUMERIC_OPS),
            "counterparty_name": FieldSpec(_counterparty_name_expr(), TEXT_OPS),
        }
