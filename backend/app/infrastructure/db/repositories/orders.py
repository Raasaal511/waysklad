from sqlalchemy import select

from app.domain.common.exceptions import NotFoundError
from app.domain.orders.entities import Order, OrderStatus
from app.domain.orders.repository import IOrderRepository
from app.infrastructure.db.mappers.orders import OrderMapper
from app.infrastructure.db.models.orders import OrderLineModel, OrderModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository

_COMPLETED = (OrderStatus.ISSUED, OrderStatus.CANCELLED)


class SqlAlchemyOrderRepository(SqlAlchemyRepository, IOrderRepository):
    async def add(self, order: Order) -> Order:
        number = await self._next_number(OrderModel)
        model = OrderMapper.to_orm(order, self._tenant, number)
        self._session.add(model)
        await self._session.flush()
        order.id = model.id
        order.number = number
        return order

    async def save(self, order: Order) -> Order:
        model = (
            await self._session.execute(
                select(OrderModel).where(
                    OrderModel.tenant_id == self._tenant, OrderModel.id == order.id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Заказ {order.id} не найден")
        model.status = order.status
        model.warehouse_id = order.warehouse_id
        model.source = order.source
        model.due_date = order.due_date
        model.prepayment = order.prepayment.amount
        model.note = order.note
        model.sale_id = order.sale_id
        model.lines = [
            OrderLineModel(
                tenant_id=self._tenant,
                product_id=line.product_id,
                variant_id=line.variant_id,
                quantity=line.quantity.value,
                price=line.price.amount,
            )
            for line in order.lines
        ]
        await self._session.flush()
        return order

    async def get(self, order_id: int) -> Order:
        model = (
            await self._session.execute(
                select(OrderModel).where(
                    OrderModel.tenant_id == self._tenant, OrderModel.id == order_id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Заказ {order_id} не найден")
        return OrderMapper.to_entity(model, await self._line_units(model))

    async def list_active(self, warehouse_ids: list[int] | None = None) -> list[Order]:
        conditions = [
            OrderModel.tenant_id == self._tenant,
            OrderModel.status.not_in(_COMPLETED),
        ]
        if warehouse_ids is not None:
            conditions.append(OrderModel.warehouse_id.in_(warehouse_ids))
        models = (
            await self._session.execute(
                select(OrderModel)
                .where(*conditions)
                .order_by(OrderModel.due_date.nulls_last(), OrderModel.id)
            )
        ).scalars().all()
        return await self._to_entities(models)

    async def list_completed(self, warehouse_ids: list[int] | None = None) -> list[Order]:
        conditions = [
            OrderModel.tenant_id == self._tenant,
            OrderModel.status.in_(_COMPLETED),
        ]
        if warehouse_ids is not None:
            conditions.append(OrderModel.warehouse_id.in_(warehouse_ids))
        models = (
            await self._session.execute(
                select(OrderModel)
                .where(*conditions)
                .order_by(OrderModel.created_at.desc())
            )
        ).scalars().all()
        return await self._to_entities(models)

    async def list_by_client(self, client_id: int) -> list[Order]:
        models = (
            await self._session.execute(
                select(OrderModel)
                .where(OrderModel.tenant_id == self._tenant, OrderModel.client_id == client_id)
                .order_by(OrderModel.created_at.desc())
            )
        ).scalars().all()
        return await self._to_entities(models)

    async def _line_units(self, model: OrderModel):
        return await self._product_unit_by_id({line.product_id for line in model.lines})

    async def _to_entities(self, models: list[OrderModel]) -> list[Order]:
        product_ids = {line.product_id for m in models for line in m.lines}
        units_by_product = await self._product_unit_by_id(product_ids)
        return [OrderMapper.to_entity(m, units_by_product) for m in models]
