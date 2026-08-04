from app.domain.common.money import Money
from app.domain.debts.entities import Debt, InstallmentPayment, Repayment
from app.infrastructure.db.models.debts import (
    DebtInstallmentModel,
    DebtModel,
    DebtRepaymentModel,
)


class DebtMapper:
    @staticmethod
    def to_orm(debt: Debt, tenant_id: int) -> DebtModel:
        return DebtModel(
            tenant_id=tenant_id,
            client_id=debt.client_id,
            sale_id=debt.sale_id,
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
                DebtRepaymentModel(tenant_id=tenant_id, amount=r.amount.amount, paid_on=r.on)
                for r in debt.repayments
            ],
        )

    @staticmethod
    def to_entity(model: DebtModel) -> Debt:
        return Debt(
            id=model.id,
            client_id=model.client_id,
            amount=Money(model.amount),
            issued_at=model.issued_at,
            due_date=model.due_date,
            sale_id=model.sale_id,
            note=model.note,
            schedule=[
                InstallmentPayment(due_date=p.due_date, amount=Money(p.amount))
                for p in model.installments
            ],
            repayments=[
                Repayment(amount=Money(r.amount), on=r.paid_on) for r in model.repayments
            ],
        )
