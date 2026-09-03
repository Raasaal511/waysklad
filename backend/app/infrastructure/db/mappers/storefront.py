from app.domain.storefront.entities import StorefrontRequest, StorefrontRequestLine
from app.infrastructure.db.models.storefront import (
    StorefrontRequestLineModel,
    StorefrontRequestModel,
)


class StorefrontRequestMapper:
    @staticmethod
    def to_orm(request: StorefrontRequest, tenant_id: int) -> StorefrontRequestModel:
        return StorefrontRequestModel(
            tenant_id=tenant_id,
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            note=request.note,
            status=request.status,
            order_id=request.order_id,
            lines=[
                StorefrontRequestLineModel(
                    tenant_id=tenant_id,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity,
                )
                for line in request.lines
            ],
        )

    @staticmethod
    def to_entity(model: StorefrontRequestModel) -> StorefrontRequest:
        return StorefrontRequest(
            id=model.id,
            customer_name=model.customer_name,
            customer_phone=model.customer_phone,
            note=model.note,
            status=model.status,
            order_id=model.order_id,
            created_at=model.created_at,
            lines=[
                StorefrontRequestLine(
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity,
                )
                for line in model.lines
            ],
        )
