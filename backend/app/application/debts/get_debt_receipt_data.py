from dataclasses import dataclass

from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Client
from app.domain.debts.entities import Debt
from app.domain.identity.entities import Tenant


@dataclass(frozen=True)
class DebtReceiptData:
    debt: Debt
    tenant: Tenant
    client: Client


class GetDebtReceiptDataUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, debt_id: int) -> DebtReceiptData:
        async with self._uow as uow:
            debt = await uow.debts.get(debt_id)
            if debt.client_id is None:
                raise DomainError("Сообщение доступно только для долга клиента")
            tenant = await uow.tenants.get(uow.tenant_id)
            client = await uow.clients.get(debt.client_id)
            return DebtReceiptData(debt=debt, tenant=tenant, client=client)
