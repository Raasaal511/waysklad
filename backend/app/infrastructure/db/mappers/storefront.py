from app.domain.storefront.entities import (
    StorefrontMessage,
    StorefrontRequest,
    StorefrontRequestLine,
)
from app.infrastructure.db.models.storefront import (
    StorefrontMessageModel,
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
            customer_telegram_chat_id=request.customer_telegram_chat_id or None,
            note=request.note,
            status=request.status,
            order_id=request.order_id,
            access_token=request.access_token,
            insufficient_stock_at_request=request.insufficient_stock_at_request,
            reservation_released=request.reservation_released,
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
            customer_telegram_chat_id=model.customer_telegram_chat_id or "",
            note=model.note,
            status=model.status,
            order_id=model.order_id,
            access_token=model.access_token,
            created_at=model.created_at,
            insufficient_stock_at_request=model.insufficient_stock_at_request,
            reservation_released=model.reservation_released,
            lines=[
                StorefrontRequestLine(
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    quantity=line.quantity,
                )
                for line in model.lines
            ],
        )


class StorefrontMessageMapper:
    @staticmethod
    def to_orm(message: StorefrontMessage, tenant_id: int) -> StorefrontMessageModel:
        return StorefrontMessageModel(
            tenant_id=tenant_id,
            request_id=message.request_id,
            author=message.author,
            text=message.text,
        )

    @staticmethod
    def to_entity(model: StorefrontMessageModel) -> StorefrontMessage:
        return StorefrontMessage(
            id=model.id,
            request_id=model.request_id,
            author=model.author,
            text=model.text,
            created_at=model.created_at,
        )
