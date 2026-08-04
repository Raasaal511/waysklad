from sqlalchemy import select

from app.domain.common.exceptions import NotFoundError
from app.domain.sales.entities import Sale
from app.domain.sales.repository import ISaleRepository
from app.infrastructure.db.mappers.sales import SaleMapper
from app.infrastructure.db.models.sales import SaleModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemySaleRepository(SqlAlchemyRepository, ISaleRepository):
    async def add(self, sale: Sale) -> Sale:
        number = await self._next_number(SaleModel)
        model = SaleMapper.to_orm(sale, self._tenant, number)
        self._session.add(model)
        await self._session.flush()
        sale.id = model.id
        return sale

    async def get(self, sale_id: int) -> Sale:
        model = (
            await self._session.execute(
                select(SaleModel).where(
                    SaleModel.tenant_id == self._tenant, SaleModel.id == sale_id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Продажа {sale_id} не найдена")
        units = await self._product_unit_by_id({line.product_id for line in model.lines})
        return SaleMapper.to_entity(model, units)
