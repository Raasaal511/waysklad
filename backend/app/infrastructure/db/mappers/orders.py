from app.domain.common.money import Money
from app.domain.common.quantity import Quantity, Unit
from app.domain.orders.entities import Order, OrderLine
from app.infrastructure.db.models.orders import OrderLineModel, OrderModel


class OrderMapper:
    @staticmethod
    def to_orm(order: Order, tenant_id: int, number: int) -> OrderModel:
        return OrderModel(
            tenant_id=tenant_id,
            number=number,
            client_id=order.client_id,
            warehouse_id=order.warehouse_id,
            status=order.status,
            source=order.source,
            due_date=order.due_date,
            prepayment=order.prepayment.amount,
            note=order.note,
            sale_id=order.sale_id,
            lines=[
                OrderLineModel(
                    tenant_id=tenant_id,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity.value,
                    price=line.price.amount,
                )
                for line in order.lines
            ],
        )

    @staticmethod
    def to_entity(model: OrderModel, units_by_product: dict[int, Unit]) -> Order:
        return Order(
            id=model.id,
            client_id=model.client_id,
            warehouse_id=model.warehouse_id,
            status=model.status,
            source=model.source,
            due_date=model.due_date,
            prepayment=Money(model.prepayment),
            note=model.note,
            number=model.number,
            sale_id=model.sale_id,
            created_at=model.created_at,
            lines=[
                OrderLine(
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=Quantity(line.quantity, units_by_product[line.product_id]),
                    price=Money(line.price),
                )
                for line in model.lines
            ],
        )
