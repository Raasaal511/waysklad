from decimal import Decimal

from sqlalchemy import select

from app.domain.inventory.entities import StockDocument
from app.domain.inventory.repository import IStockDocumentRepository, IStockRepository
from app.infrastructure.db.mappers.inventory import StockDocumentMapper
from app.infrastructure.db.models.inventory import StockDocumentModel, StockItemModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyStockRepository(SqlAlchemyRepository, IStockRepository):
    async def get(
        self, product_id: int, warehouse_id: int, variant_id: int | None = None
    ) -> Decimal:
        item = await self._get_item(product_id, warehouse_id, variant_id, for_update=False)
        return item.quantity if item else Decimal("0")

    async def change(
        self, product_id: int, warehouse_id: int, delta: Decimal, variant_id: int | None = None
    ) -> Decimal:
        item = await self._get_item(product_id, warehouse_id, variant_id, for_update=True)
        if item is None:
            item = StockItemModel(
                tenant_id=self._tenant,
                product_id=product_id,
                variant_id=variant_id,
                warehouse_id=warehouse_id,
                quantity=delta,
            )
            self._session.add(item)
        else:
            item.quantity = item.quantity + delta
        await self._session.flush()
        return item.quantity

    async def _get_item(
        self, product_id: int, warehouse_id: int, variant_id: int | None, for_update: bool
    ) -> StockItemModel | None:
        stmt = select(StockItemModel).where(
            StockItemModel.tenant_id == self._tenant,
            StockItemModel.product_id == product_id,
            StockItemModel.warehouse_id == warehouse_id,
            StockItemModel.variant_id.is_(None)
            if variant_id is None
            else StockItemModel.variant_id == variant_id,
        )
        if for_update:  # блокировка строки: два продавца не спишут один остаток дважды
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()


class SqlAlchemyStockDocumentRepository(SqlAlchemyRepository, IStockDocumentRepository):
    async def add(self, document: StockDocument) -> StockDocument:
        number = await self._next_number(StockDocumentModel)
        model = StockDocumentMapper.to_orm(document, self._tenant, number)
        self._session.add(model)
        await self._session.flush()
        document.id = model.id
        return document
