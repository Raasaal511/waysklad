from app.domain.common.money import Money
from app.domain.common.quantity import Quantity, Unit
from app.domain.sales.entities import Sale, SaleLine
from app.infrastructure.db.models.sales import SaleLineModel, SaleModel


class SaleMapper:
    @staticmethod
    def to_orm(sale: Sale, tenant_id: int, number: int) -> SaleModel:
        return SaleModel(
            tenant_id=tenant_id,
            number=number,
            warehouse_id=sale.warehouse_id,
            seller_id=sale.seller_id,
            client_id=sale.client_id,
            payment_method=sale.payment_method,
            discount=sale.discount.amount,
            total=sale.total.amount,  # снимок суммы чека для аналитики
            lines=[
                SaleLineModel(
                    tenant_id=tenant_id,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity.value,
                    price=line.price.amount,
                    # TODO (сессия 03): снимок закупочной цены для расчёта прибыли
                )
                for line in sale.lines
            ],
        )

    @staticmethod
    def to_entity(model: SaleModel, units_by_product: dict[int, Unit]) -> Sale:
        return Sale(
            id=model.id,
            warehouse_id=model.warehouse_id,
            seller_id=model.seller_id,
            payment_method=model.payment_method,
            discount=Money(model.discount),
            client_id=model.client_id,
            created_at=model.created_at,
            lines=[
                SaleLine(
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=Quantity(line.quantity, units_by_product[line.product_id]),
                    price=Money(line.price),
                )
                for line in model.lines
            ],
        )
