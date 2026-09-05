from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import exists, func, select

from app.domain.common.exceptions import NotFoundError
from app.domain.common.quantity import Unit
from app.domain.sales.entities import Sale, SaleReturn
from app.domain.sales.payment import PaymentMethod
from app.domain.sales.repository import ISaleRepository, ISaleReturnRepository
from app.infrastructure.db.mappers.sales import SaleMapper, SaleReturnMapper
from app.infrastructure.db.models.sales import SaleLineModel, SaleModel, SaleReturnModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository

_SORT_COLUMNS = {
    "date_desc": SaleModel.created_at.desc(),
    "date_asc": SaleModel.created_at.asc(),
    "payment": (SaleModel.payment_method, SaleModel.created_at.desc()),
}


class SqlAlchemySaleRepository(SqlAlchemyRepository, ISaleRepository):
    async def add(self, sale: Sale) -> Sale:
        number = await self._next_number(SaleModel)
        model = SaleMapper.to_orm(sale, self._tenant, number)
        self._session.add(model)
        await self._session.flush()
        sale.id = model.id
        for entity, line_model in zip(sale.lines, model.lines):
            entity.id = line_model.id
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

    async def get_by_client_op_id(self, client_op_id: str) -> Sale | None:
        model = (
            await self._session.execute(
                select(SaleModel).where(
                    SaleModel.tenant_id == self._tenant,
                    SaleModel.client_op_id == client_op_id,
                )
            )
        ).scalar_one_or_none()
        if model is None:
            return None
        units = await self._product_unit_by_id({line.product_id for line in model.lines})
        return SaleMapper.to_entity(model, units)

    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
        client_id: int | None = None,
        product_id: int | None = None,
        warehouse_id: int | None = None,
        warehouse_ids: list[int] | None = None,
        payment_method: PaymentMethod | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort: str = "date_desc",
    ) -> tuple[list[Sale], int]:
        conditions = [SaleModel.tenant_id == self._tenant, SaleModel.deleted_at.is_(None)]
        if client_id is not None:
            conditions.append(SaleModel.client_id == client_id)
        if product_id is not None:
            conditions.append(
                exists().where(
                    SaleLineModel.sale_id == SaleModel.id,
                    SaleLineModel.product_id == product_id,
                )
            )
        if warehouse_id is not None:
            conditions.append(SaleModel.warehouse_id == warehouse_id)
        if warehouse_ids is not None:
            conditions.append(SaleModel.warehouse_id.in_(warehouse_ids))
        if payment_method is not None:
            conditions.append(SaleModel.payment_method == payment_method)
        if date_from is not None:
            conditions.append(SaleModel.created_at >= datetime.combine(date_from, time.min))
        if date_to is not None:
            conditions.append(SaleModel.created_at <= datetime.combine(date_to, time.max))

        total = (
            await self._session.execute(
                select(func.count()).select_from(SaleModel).where(*conditions)
            )
        ).scalar_one()

        order = _SORT_COLUMNS.get(sort, _SORT_COLUMNS["date_desc"])
        order_by = order if isinstance(order, tuple) else (order,)
        models = (
            await self._session.execute(
                select(SaleModel)
                .where(*conditions)
                .order_by(*order_by)
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        product_ids = {line.product_id for model in models for line in model.lines}
        units = await self._product_unit_by_id(product_ids)
        return [SaleMapper.to_entity(m, units) for m in models], total

    async def summary_by_payment_method(
        self,
        warehouse_id: int | None = None,
        warehouse_ids: list[int] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[PaymentMethod, tuple[int, Decimal]]:
        conditions = [SaleModel.tenant_id == self._tenant, SaleModel.deleted_at.is_(None)]
        if warehouse_id is not None:
            conditions.append(SaleModel.warehouse_id == warehouse_id)
        if warehouse_ids is not None:
            conditions.append(SaleModel.warehouse_id.in_(warehouse_ids))
        if date_from is not None:
            conditions.append(SaleModel.created_at >= datetime.combine(date_from, time.min))
        if date_to is not None:
            conditions.append(SaleModel.created_at <= datetime.combine(date_to, time.max))

        rows = (
            await self._session.execute(
                select(SaleModel.payment_method, func.count(), func.coalesce(func.sum(SaleModel.total), 0))
                .where(*conditions)
                .group_by(SaleModel.payment_method)
            )
        ).all()
        return {method: (count, total) for method, count, total in rows}

    async def save(self, sale: Sale) -> None:
        model = (
            await self._session.execute(
                select(SaleModel).where(
                    SaleModel.tenant_id == self._tenant, SaleModel.id == sale.id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Продажа {sale.id} не найдена")
        model.client_id = sale.client_id
        model.note = sale.note
        model.deleted_at = sale.deleted_at


class SqlAlchemySaleReturnRepository(SqlAlchemyRepository, ISaleReturnRepository):
    async def add(self, sale_return: SaleReturn) -> SaleReturn:
        model = SaleReturnMapper.to_orm(sale_return, self._tenant)
        self._session.add(model)
        await self._session.flush()
        sale_return.id = model.id
        for entity, line_model in zip(sale_return.lines, model.lines):
            entity.id = line_model.id
        return sale_return

    async def list_by_sale(self, sale_id: int) -> list[SaleReturn]:
        models = (
            await self._session.execute(
                select(SaleReturnModel).where(
                    SaleReturnModel.tenant_id == self._tenant,
                    SaleReturnModel.sale_id == sale_id,
                )
            )
        ).scalars().all()
        sale_line_ids = {line.sale_line_id for model in models for line in model.lines}
        units = await self._units_by_sale_line(sale_line_ids)
        return [SaleReturnMapper.to_entity(m, units) for m in models]

    async def get_by_client_op_id(self, client_op_id: str) -> SaleReturn | None:
        model = (
            await self._session.execute(
                select(SaleReturnModel).where(
                    SaleReturnModel.tenant_id == self._tenant,
                    SaleReturnModel.client_op_id == client_op_id,
                )
            )
        ).scalar_one_or_none()
        if model is None:
            return None
        sale_line_ids = {line.sale_line_id for line in model.lines}
        units = await self._units_by_sale_line(sale_line_ids)
        return SaleReturnMapper.to_entity(model, units)

    async def _units_by_sale_line(self, sale_line_ids: set[int]):
        if not sale_line_ids:
            return {}
        rows = (
            await self._session.execute(
                select(SaleLineModel.id, SaleLineModel.product_id).where(
                    SaleLineModel.id.in_(sale_line_ids)
                )
            )
        ).all()
        product_units = await self._product_unit_by_id({product_id for _, product_id in rows})
        fallback = Unit("pcs", "шт")
        return {line_id: product_units.get(product_id, fallback) for line_id, product_id in rows}
