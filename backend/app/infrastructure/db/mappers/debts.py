from app.domain.common.money import Money
from app.domain.debts.entities import Debt, DebtExtension, InstallmentPayment, Repayment
from app.infrastructure.db.models.debts import (
    DebtExtensionModel,
    DebtInstallmentModel,
    DebtModel,
    DebtRepaymentModel,
)


class DebtMapper:
    @staticmethod
    def to_orm(debt: Debt, tenant_id: int) -> DebtModel:
        return DebtModel(
            tenant_id=tenant_id,
            warehouse_id=debt.warehouse_id,
            client_id=debt.client_id,
            supplier_id=debt.supplier_id,
            sale_id=debt.sale_id,
            receipt_document_id=debt.receipt_document_id,
            amount=debt.amount.amount,
            issued_at=debt.issued_at,
            due_date=debt.due_date,
            note=debt.note,
            installments=[
                DebtInstallmentModel(
                    tenant_id=tenant_id, due_date=p.due_date, amount=p.amount.amount
                )
                for p in debt.schedule
            ],
            repayments=[
                DebtRepaymentModel(
                    tenant_id=tenant_id,
                    amount=r.amount.amount,
                    paid_on=r.on,
                    note=r.note,
                    author_id=r.author_id,
                )
                for r in debt.repayments
            ],
            extensions=[
                DebtExtensionModel(
                    tenant_id=tenant_id,
                    old_due_date=e.old_due_date,
                    new_due_date=e.new_due_date,
                    reason=e.reason,
                    author_id=e.author_id,
                    created_at=e.created_at,
                )
                for e in debt.extensions
            ],
        )

    @staticmethod
    def to_entity(model: DebtModel) -> Debt:
        return Debt(
            id=model.id,
            warehouse_id=model.warehouse_id,
            client_id=model.client_id,
            supplier_id=model.supplier_id,
            amount=Money(model.amount),
            issued_at=model.issued_at,
            due_date=model.due_date,
            sale_id=model.sale_id,
            receipt_document_id=model.receipt_document_id,
            note=model.note,
            schedule=[
                InstallmentPayment(due_date=p.due_date, amount=Money(p.amount))
                for p in model.installments
            ],
            repayments=[
                Repayment(amount=Money(r.amount), on=r.paid_on, note=r.note, author_id=r.author_id)
                for r in model.repayments
            ],
            extensions=[
                DebtExtension(
                    old_due_date=e.old_due_date,
                    new_due_date=e.new_due_date,
                    reason=e.reason,
                    author_id=e.author_id,
                    created_at=e.created_at,
                )
                for e in model.extensions
            ],
        )
