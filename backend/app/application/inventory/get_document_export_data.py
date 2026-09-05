from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.inventory.entities import StockDocument


@dataclass(frozen=True)
class DocumentExportData:
    documents: list[StockDocument]
    warehouse_names: dict[int, str]
    product_names: dict[int, str]
    product_fractional: dict[int, bool]
    user_names: dict[int, str]
    shop_name: str


class GetDocumentExportDataUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> DocumentExportData:
        async with self._uow as uow:
            warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
            documents = await uow.stock_documents.list_all(warehouse_ids)
            warehouses = await uow.warehouses.list()
            products = await uow.products.search_all()
            users = await uow.users.list_by_tenant()
            tenant = await uow.tenants.get(uow.tenant_id)
            return DocumentExportData(
                documents=documents,
                warehouse_names={w.id: w.name for w in warehouses},
                product_names={p.id: p.name for p in products},
                product_fractional={p.id: p.unit.fractional for p in products},
                user_names={u.id: u.name for u in users},
                shop_name=tenant.name,
            )
