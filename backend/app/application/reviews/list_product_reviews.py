from dataclasses import dataclass

from app.domain.reviews.entities import Review
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class ListProductReviewsCommand:
    slug: str
    product_id: int


@dataclass(frozen=True)
class ProductReviewsResult:
    reviews: list[Review]
    average_rating: float
    reviews_count: int


class ListProductReviewsUseCase:
    """Публичный (без авторизации) список видимых отзывов на товар — для
    карточки товара на витрине. Скрытые владельцем (is_hidden) не отдаются
    и не входят в агрегат рейтинга."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: ListProductReviewsCommand) -> ProductReviewsResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return None

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            reviews = await uow.reviews.list_by_product(cmd.product_id)

        count = len(reviews)
        average = sum(r.rating for r in reviews) / count if count else 0.0
        return ProductReviewsResult(reviews=reviews, average_rating=average, reviews_count=count)
