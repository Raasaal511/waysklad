from typing import Literal

from pydantic import BaseModel, Field

from app.application.reviews.check_review_eligibility import ReviewEligibilityResult
from app.application.reviews.create_review import CreateReviewCommand
from app.application.reviews.list_all_reviews_for_owner import (
    AllReviewsForOwnerResult,
    ListAllReviewsForOwnerCommand,
)
from app.application.reviews.list_product_reviews import ProductReviewsResult
from app.application.reviews.list_reviews_for_owner import OwnerReviewsResult
from app.application.reviews.vote_review import VoteReviewResult
from app.domain.reviews.entities import Review, MAX_PHOTOS, MAX_TAGS
from app.domain.reviews.repository import (
    ProductRatingAggregate,
    PublicReviewListFilter,
    PublicReviewListResult,
)
from app.domain.reviews.tags import REVIEW_TAGS, label_for

ReviewSort = Literal["date_desc", "date_asc", "rating_desc", "rating_asc", "useful"]
ReviewStatus = Literal["all", "visible", "hidden"]


class ReviewTagResponse(BaseModel):
    code: str
    label: str


class ReviewTagCountResponse(BaseModel):
    code: str
    label: str
    count: int


class ReviewPhotoFeedResponse(BaseModel):
    url: str
    review_id: int


class CreateReviewRequest(BaseModel):
    storefront_request_id: int
    product_id: int
    rating: int = Field(ge=1, le=5)
    text: str = Field("", max_length=2000)
    photo: str = ""  # устаревшее — совместимость со старыми клиентами, см. photos
    photos: list[str] = Field(default_factory=list, max_length=MAX_PHOTOS)
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS)

    model_config = {"extra": "forbid"}

    def to_command(self, customer_id: int) -> CreateReviewCommand:
        return CreateReviewCommand(
            customer_id=customer_id,
            storefront_request_id=self.storefront_request_id,
            product_id=self.product_id,
            rating=self.rating,
            text=self.text,
            photo=self.photo,
            photos=self.photos,
            tags=self.tags,
        )


class UploadReviewPhotoResponse(BaseModel):
    url: str


class VoteReviewRequest(BaseModel):
    value: Literal[1, -1, 0]

    model_config = {"extra": "forbid"}


class VoteReviewResponse(BaseModel):
    likes: int
    dislikes: int
    my_vote: int

    @classmethod
    def from_result(cls, result: VoteReviewResult) -> "VoteReviewResponse":
        return cls(likes=result.likes, dislikes=result.dislikes, my_vote=result.my_vote)


class ReviewResponse(BaseModel):
    id: int
    product_id: int
    rating: int
    text: str
    author_name: str
    photo: str  # устаревшее — photo = photos[0] или "", см. photos
    photos: list[str]
    tags: list[ReviewTagResponse]
    likes: int
    dislikes: int
    my_vote: int  # 0, если без токена или голоса нет
    created_at: str | None
    is_hidden: bool | None = None  # None на публичном списке — владелец видит скрытость, покупатель нет

    @classmethod
    def from_entity(
        cls,
        review: Review,
        *,
        include_hidden_flag: bool = False,
        likes: int = 0,
        dislikes: int = 0,
        my_vote: int = 0,
    ) -> "ReviewResponse":
        return cls(
            id=review.id,
            product_id=review.product_id,
            rating=review.rating,
            text=review.text,
            author_name=review.author_name,
            photo=review.photo,
            photos=review.photos,
            tags=[ReviewTagResponse(code=code, label=label_for(code)) for code in review.tags],
            likes=likes,
            dislikes=dislikes,
            my_vote=my_vote,
            created_at=review.created_at.isoformat() if review.created_at else None,
            is_hidden=review.is_hidden if include_hidden_flag else None,
        )


class OwnerReviewResponse(ReviewResponse):
    product_name: str | None = None  # только в общем списке модерации (GET /api/reviews), не в /product/{id}


class ProductRatingResponse(BaseModel):
    average_rating: float
    reviews_count: int

    @classmethod
    def from_aggregate(cls, aggregate: ProductRatingAggregate) -> "ProductRatingResponse":
        return cls(average_rating=aggregate.average_rating, reviews_count=aggregate.reviews_count)


class StorefrontProductReviewsParams(BaseModel):
    sort: ReviewSort = "date_desc"
    rating: int | None = Field(None, ge=1, le=5)
    with_photos: bool = False
    tag: str | None = None
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0)

    model_config = {"extra": "forbid"}

    def to_filter(self) -> PublicReviewListFilter:
        return PublicReviewListFilter(
            sort=self.sort,
            rating=self.rating,
            with_photos=self.with_photos,
            tag=self.tag,
            limit=self.limit,
            offset=self.offset,
        )


class ProductReviewsResponse(BaseModel):
    reviews: list[ReviewResponse]
    total: int
    average_rating: float
    reviews_count: int
    rating_distribution: dict[str, int]
    with_photos_count: int
    tags: list[ReviewTagCountResponse]
    photos: list[ReviewPhotoFeedResponse]

    @classmethod
    def from_result(cls, result: ProductReviewsResult) -> "ProductReviewsResponse":
        list_result: PublicReviewListResult = result.list_result
        reviews = []
        for review in list_result.reviews:
            likes, dislikes = list_result.votes.get(review.id, (0, 0)) if review.id else (0, 0)
            my_vote = result.my_votes.get(review.id, 0) if review.id else 0
            reviews.append(
                ReviewResponse.from_entity(review, likes=likes, dislikes=dislikes, my_vote=my_vote)
            )
        return cls(
            reviews=reviews,
            total=list_result.total,
            average_rating=list_result.average_rating,
            reviews_count=list_result.reviews_count,
            rating_distribution=list_result.rating_distribution,
            with_photos_count=list_result.with_photos_count,
            tags=[
                ReviewTagCountResponse(code=t.code, label=label_for(t.code), count=t.count)
                for t in list_result.tags
            ],
            photos=[ReviewPhotoFeedResponse(url=p.url, review_id=p.review_id) for p in list_result.photos],
        )


class ReviewEligibilityResponse(BaseModel):
    can_review: bool
    request_id: int | None
    reason: Literal["ok", "no_purchase", "already_reviewed"]

    @classmethod
    def from_result(cls, result: ReviewEligibilityResult) -> "ReviewEligibilityResponse":
        return cls(can_review=result.can_review, request_id=result.request_id, reason=result.reason)


class OwnerProductReviewsResponse(BaseModel):
    """Ответ GET /api/reviews/product/{id} — все отзывы товара для владельца."""

    reviews: list[ReviewResponse]

    @classmethod
    def from_result(cls, result: OwnerReviewsResult) -> "OwnerProductReviewsResponse":
        reviews = []
        for review in result.reviews:
            likes, dislikes = result.votes.get(review.id, (0, 0)) if review.id else (0, 0)
            reviews.append(
                ReviewResponse.from_entity(
                    review, include_hidden_flag=True, likes=likes, dislikes=dislikes
                )
            )
        return cls(reviews=reviews)


class AllReviewsForOwnerParams(BaseModel):
    status: ReviewStatus = "all"
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)

    model_config = {"extra": "forbid"}

    def to_command(self) -> ListAllReviewsForOwnerCommand:
        return ListAllReviewsForOwnerCommand(status=self.status, limit=self.limit, offset=self.offset)


class AllReviewsForOwnerResponse(BaseModel):
    """Ответ GET /api/reviews?status=... — экран модерации по всему магазину."""

    reviews: list[OwnerReviewResponse]
    total: int

    @classmethod
    def from_result(cls, result: AllReviewsForOwnerResult) -> "AllReviewsForOwnerResponse":
        reviews = []
        for review in result.reviews:
            base = ReviewResponse.from_entity(review, include_hidden_flag=True)
            reviews.append(
                OwnerReviewResponse(
                    **base.model_dump(),
                    product_name=result.product_names.get(review.product_id),
                )
            )
        return cls(reviews=reviews, total=result.total)


def all_review_tags() -> list[ReviewTagResponse]:
    return [ReviewTagResponse(code=t.code, label=t.label) for t in REVIEW_TAGS]
