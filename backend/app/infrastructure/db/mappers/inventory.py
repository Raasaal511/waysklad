from datetime import datetime, timezone

from app.domain.common.money import Money
from app.domain.common.quantity import Quantity, Unit
from app.domain.inventory.entities import StockDocument, StockLine
from app.infrastructure.db.models.inventory import (
    StockDocumentLineModel,
    StockDocumentModel,
)


class StockDocumentMapper:
    @staticmethod
    def to_orm(document: StockDocument, tenant_id: int, number: int) -> StockDocumentModel:
        return StockDocumentModel(
            tenant_id=tenant_id,
            number=number,
            type=document.type,
            warehouse_id=document.warehouse_id,
            to_warehouse_id=document.to_warehouse_id,
            supplier_id=document.supplier_id,
            author_id=document.author_id,
            note=document.note,
            posted=document.posted,
            posted_at=datetime.now(timezone.utc).replace(tzinfo=None)
            if document.posted
            else None,
            client_op_id=document.client_op_id,
            lines=[
                StockDocumentLineModel(
                    tenant_id=tenant_id,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity.value,
                    cost=line.cost.amount if line.cost else None,
                )
                for line in document.lines
            ],
        )

    @staticmethod
    def to_entity(
        model: StockDocumentModel, units_by_product: dict[int, Unit]
    ) -> StockDocument:
        return StockDocument(
            id=model.id,
            type=model.type,
            warehouse_id=model.warehouse_id,
            author_id=model.author_id,
            to_warehouse_id=model.to_warehouse_id,
            supplier_id=model.supplier_id,
            note=model.note,
            posted=model.posted,
            number=model.number,
            created_at=model.created_at,
            client_op_id=model.client_op_id,
            lines=[
                StockLine(
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=Quantity(line.quantity, units_by_product[line.product_id]),
                    cost=Money(line.cost) if line.cost is not None else None,
                )
                for line in model.lines
            ],
        )
