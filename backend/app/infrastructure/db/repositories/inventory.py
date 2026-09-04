from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.domain.common.exceptions import NotFoundError
from app.domain.inventory.entities import StockDocument, StockItem
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
        item = await self._get_or_create(product_id, warehouse_id, variant_id)
        item.quantity = item.quantity + delta
        await self._session.flush()
        return item.quantity

    async def reserve(
        self, product_id: int, warehouse_id: int, delta: Decimal, variant_id: int | None = None
    ) -> Decimal:
        item = await self._get_or_create(product_id, warehouse_id, variant_id)
        item.reserved = item.reserved + delta
        await self._session.flush()
        return item.reserved

    async def _get_or_create(
        self, product_id: int, warehouse_id: int, variant_id: int | None
    ) -> StockItemModel:
        """Первая операция над товаром/складом создаёт строку остатка — если
        это делают одновременно два запроса (например, две приёмки на разные
        склады сразу после заведения товара), второй INSERT бьётся об уникальный
        индекс. Savepoint даёт откатить только эту вставку, не всю транзакцию
        use case, и перечитать уже созданную строку под блокировкой."""
        item = await self._get_item(product_id, warehouse_id, variant_id, for_update=True)
        if item is not None:
            return item
        try:
            async with self._session.begin_nested():
                item = StockItemModel(
                    tenant_id=self._tenant,
                    product_id=product_id,
                    variant_id=variant_id,
                    warehouse_id=warehouse_id,
                    quantity=Decimal("0"),
                )
                self._session.add(item)
                await self._session.flush()
        except IntegrityError:
            item = await self._get_item(product_id, warehouse_id, variant_id, for_update=True)
            if item is None:
                raise
        return item

    async def get_reserved(
        self, product_id: int, warehouse_id: int, variant_id: int | None = None
    ) -> Decimal:
        item = await self._get_item(product_id, warehouse_id, variant_id, for_update=False)
        return item.reserved if item else Decimal("0")

    async def list_all(self) -> list[StockItem]:
        models = (
            await self._session.execute(
                select(StockItemModel).where(
                    StockItemModel.tenant_id == self._tenant,
                    StockItemModel.quantity != 0,
                )
            )
        ).scalars()
        return [
            StockItem(
                product_id=m.product_id, warehouse_id=m.warehouse_id,
                quantity=m.quantity, variant_id=m.variant_id, reserved=m.reserved,
            )
            for m in models
        ]

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

    async def list_all(self, warehouse_ids: list[int] | None = None) -> list[StockDocument]:
        conditions = [StockDocumentModel.tenant_id == self._tenant]
        if warehouse_ids is not None:
            conditions.append(
                or_(
                    StockDocumentModel.warehouse_id.in_(warehouse_ids),
                    StockDocumentModel.to_warehouse_id.in_(warehouse_ids),
                )
            )
        models = (
            await self._session.execute(
                select(StockDocumentModel)
                .where(*conditions)
                .order_by(StockDocumentModel.created_at.desc())
            )
        ).scalars().all()

        product_ids = {line.product_id for m in models for line in m.lines}
        units_by_product = await self._product_unit_by_id(product_ids)
        return [StockDocumentMapper.to_entity(m, units_by_product) for m in models]

    async def get(self, document_id: int) -> StockDocument:
        model = (
            await self._session.execute(
                select(StockDocumentModel).where(
                    StockDocumentModel.tenant_id == self._tenant,
                    StockDocumentModel.id == document_id,
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Документ {document_id} не найден")
        product_ids = {line.product_id for line in model.lines}
        units_by_product = await self._product_unit_by_id(product_ids)
        return StockDocumentMapper.to_entity(model, units_by_product)
