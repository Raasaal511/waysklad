from app.domain.reviews.entities import Review
from app.infrastructure.db.models.reviews import ReviewModel


class ReviewMapper:
    @staticmethod
    def to_orm(review: Review, tenant_id: int) -> ReviewModel:
        return ReviewModel(
            tenant_id=tenant_id,
            product_id=review.product_id,
            storefront_request_id=review.storefront_request_id,
            customer_id=review.customer_id,
            rating=review.rating,
            text=review.text,
            author_name=review.author_name,
            photo=review.photo,
            is_hidden=review.is_hidden,
        )

    @staticmethod
    def to_entity(model: ReviewModel) -> Review:
        return Review(
            id=model.id,
            tenant_id=model.tenant_id,
            product_id=model.product_id,
            storefront_request_id=model.storefront_request_id,
            customer_id=model.customer_id,
            rating=model.rating,
            text=model.text,
            author_name=model.author_name,
            photo=model.photo,
            is_hidden=model.is_hidden,
            created_at=model.created_at,
        )
