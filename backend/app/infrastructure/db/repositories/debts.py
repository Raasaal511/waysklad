from datetime import date

from sqlalchemy import select

from app.domain.common.exceptions import NotFoundError
from app.domain.debts.entities import Debt
from app.domain.debts.repository import IDebtRepository
from app.infrastructure.db.mappers.debts import DebtMapper
from app.infrastructure.db.models.debts import (
    DebtInstallmentModel,
    DebtModel,
    DebtRepaymentModel,
)
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyDebtRepository(SqlAlchemyRepository, IDebtRepository):
    async def add(self, debt: Debt) -> Debt:
        model = DebtMapper.to_orm(debt, self._tenant)
        self._session.add(model)
        await self._session.flush()
        debt.id = model.id
        return debt

    async def save(self, debt: Debt) -> Debt:
        model = (
            await self._session.execute(
                select(DebtModel).where(
                    DebtModel.tenant_id == self._tenant, DebtModel.id == debt.id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Долг {debt.id} не найден")
        model.due_date = debt.due_date
        model.note = debt.note
        # погашения только дописываются — историю не переписываем
        for repayment in debt.repayments[len(model.repayments):]:
            model.repayments.append(
                DebtRepaymentModel(
                    tenant_id=self._tenant,
                    amount=repayment.amount.amount,
                    paid_on=repayment.on,
                )
            )
        # график рассрочки заменяется целиком (delete-orphan удалит старый)
        model.installments = [
            DebtInstallmentModel(
                tenant_id=self._tenant, due_date=p.due_date, amount=p.amount.amount
            )
            for p in debt.schedule
        ]
        await self._session.flush()
        return debt

    async def get(self, debt_id: int) -> Debt:
        model = (
            await self._session.execute(
                select(DebtModel).where(
                    DebtModel.tenant_id == self._tenant, DebtModel.id == debt_id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Долг {debt_id} не найден")
        return DebtMapper.to_entity(model)

    async def list_by_client(self, client_id: int) -> list[Debt]:
        models = (
            await self._session.execute(
                select(DebtModel)
                .where(DebtModel.tenant_id == self._tenant, DebtModel.client_id == client_id)
                .order_by(DebtModel.issued_at)
            )
        ).scalars().all()
        return [DebtMapper.to_entity(m) for m in models]

    async def list_by_supplier(self, supplier_id: int) -> list[Debt]:
        models = (
            await self._session.execute(
                select(DebtModel)
                .where(DebtModel.tenant_id == self._tenant, DebtModel.supplier_id == supplier_id)
                .order_by(DebtModel.issued_at)
            )
        ).scalars().all()
        return [DebtMapper.to_entity(m) for m in models]

    async def list_due(self, on: date) -> list[Debt]:
        models = (
            await self._session.execute(
                select(DebtModel).where(
                    DebtModel.tenant_id == self._tenant, DebtModel.due_date == on
                )
            )
        ).scalars().all()
        return [debt for debt in map(DebtMapper.to_entity, models) if not debt.is_closed]
