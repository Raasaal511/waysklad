from pydantic import BaseModel, Field

from app.application.reviews.create_review import CreateReviewCommand
from app.application.reviews.list_product_reviews import ProductReviewsResult
from app.domain.reviews.entities import Review
from app.domain.reviews.repository import ProductRatingAggregate


class CreateReviewRequest(BaseModel):
    storefront_request_id: int
    product_id: int
    rating: int = Field(ge=1, le=5)
    text: str = Field("", max_length=2000)
    photo: str = ""

    model_config = {"extra": "forbid"}

    def to_command(self, customer_id: int) -> CreateReviewCommand:
        return CreateReviewCommand(
            customer_id=customer_id,
            storefront_request_id=self.storefront_request_id,
            product_id=self.product_id,
            rating=self.rating,
            text=self.text,
            photo=self.photo,
        )


class ReviewResponse(BaseModel):
    id: int
    product_id: int
    rating: int
    text: str
    author_name: str
    photo: str
    created_at: str | None
    is_hidden: bool | None = None  # None на публичном списке — владелец видит скрытость, покупатель нет

    @classmethod
    def from_entity(cls, review: Review, *, include_hidden_flag: bool = False) -> "ReviewResponse":
        return cls(
            id=review.id,
            product_id=review.product_id,
            rating=review.rating,
            text=review.text,
            author_name=review.author_name,
            photo=review.photo,
            created_at=review.created_at.isoformat() if review.created_at else None,
            is_hidden=review.is_hidden if include_hidden_flag else None,
        )


class ProductRatingResponse(BaseModel):
    average_rating: float
    reviews_count: int

    @classmethod
    def from_aggregate(cls, aggregate: ProductRatingAggregate) -> "ProductRatingResponse":
        return cls(average_rating=aggregate.average_rating, reviews_count=aggregate.reviews_count)


class ProductReviewsResponse(BaseModel):
    reviews: list[ReviewResponse]
    average_rating: float
    reviews_count: int

    @classmethod
    def from_result(cls, result: ProductReviewsResult) -> "ProductReviewsResponse":
        return cls(
            reviews=[ReviewResponse.from_entity(r) for r in result.reviews],
            average_rating=result.average_rating,
            reviews_count=result.reviews_count,
        )
