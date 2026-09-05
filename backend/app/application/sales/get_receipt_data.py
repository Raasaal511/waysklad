from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Client
from app.domain.identity.entities import Tenant
from app.domain.sales.entities import Sale


@dataclass(frozen=True)
class ReceiptData:
    sale: Sale
    tenant: Tenant
    product_names: dict[int, str]
    client: Client | None


class GetReceiptDataUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, sale_id: int) -> ReceiptData:
        async with self._uow as uow:
            sale = await uow.sales.get(sale_id)
            tenant = await uow.tenants.get(uow.tenant_id)
            product_names = {
                product_id: (await uow.products.get(product_id)).name
                for product_id in {line.product_id for line in sale.lines}
            }
            client = await uow.clients.get(sale.client_id) if sale.client_id else None
            return ReceiptData(sale=sale, tenant=tenant, product_names=product_names, client=client)
