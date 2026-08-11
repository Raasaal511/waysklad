from app.domain.common.money import Money
from app.domain.common.quantity import Quantity, Unit
from app.domain.sales.entities import Sale, SaleLine, SaleReturn, SaleReturnLine
from app.infrastructure.db.models.sales import (
    SaleLineModel,
    SaleModel,
    SaleReturnLineModel,
    SaleReturnModel,
)


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
            client_op_id=sale.client_op_id,
            note=sale.note,
            cash_received=sale.cash_received.amount if sale.cash_received is not None else None,
            lines=[
                SaleLineModel(
                    tenant_id=tenant_id,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity.value,
                    price=line.price.amount,
                    purchase_price=line.purchase_price.amount,
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
            client_op_id=model.client_op_id,
            note=model.note,
            deleted_at=model.deleted_at,
            cash_received=Money(model.cash_received) if model.cash_received is not None else None,
            lines=[
                SaleLine(
                    id=line.id,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=Quantity(line.quantity, units_by_product[line.product_id]),
                    price=Money(line.price),
                    purchase_price=Money(line.purchase_price),
                )
                for line in model.lines
            ],
        )


class SaleReturnMapper:
    @staticmethod
    def to_orm(sale_return: SaleReturn, tenant_id: int) -> SaleReturnModel:
        return SaleReturnModel(
            tenant_id=tenant_id,
            sale_id=sale_return.sale_id,
            author_id=sale_return.author_id,
            note=sale_return.note,
            lines=[
                SaleReturnLineModel(
                    tenant_id=tenant_id,
                    sale_line_id=line.sale_line_id,
                    quantity=line.quantity.value,
                )
                for line in sale_return.lines
            ],
        )

    @staticmethod
    def to_entity(model: SaleReturnModel, units_by_sale_line: dict[int, Unit]) -> SaleReturn:
        return SaleReturn(
            id=model.id,
            sale_id=model.sale_id,
            author_id=model.author_id,
            note=model.note,
            created_at=model.created_at,
            lines=[
                SaleReturnLine(
                    id=line.id,
                    sale_line_id=line.sale_line_id,
                    quantity=Quantity(line.quantity, units_by_sale_line[line.sale_line_id]),
                )
                for line in model.lines
            ],
        )
