from sqlalchemy import func, select

from app.domain.common.exceptions import NotFoundError
from app.domain.reviews.entities import Review
from app.domain.reviews.repository import IReviewRepository, ProductRatingAggregate
from app.infrastructure.db.mappers.reviews import ReviewMapper
from app.infrastructure.db.models.reviews import ReviewModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyReviewRepository(SqlAlchemyRepository, IReviewRepository):
    async def add(self, review: Review) -> Review:
        model = ReviewMapper.to_orm(review, self._tenant)
        self._session.add(model)
        await self._session.flush()
        review.id = model.id
        review.created_at = model.created_at
        return review

    async def get(self, review_id: int) -> Review:
        model = await self._get_model(review_id)
        if model is None:
            raise NotFoundError(f"Отзыв {review_id} не найден")
        return ReviewMapper.to_entity(model)

    async def exists_for_request(self, storefront_request_id: int) -> bool:
        result = await self._session.execute(
            select(ReviewModel.id).where(
                ReviewModel.storefront_request_id == storefront_request_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_by_product(
        self, product_id: int, *, include_hidden: bool = False
    ) -> list[Review]:
        conditions = [
            ReviewModel.tenant_id == self._tenant,
            ReviewModel.product_id == product_id,
        ]
        if not include_hidden:
            conditions.append(ReviewModel.is_hidden.is_(False))
        models = (
            await self._session.execute(
                select(ReviewModel).where(*conditions).order_by(ReviewModel.created_at.desc())
            )
        ).scalars().all()
        return [ReviewMapper.to_entity(m) for m in models]

    async def set_hidden(self, review_id: int, is_hidden: bool) -> Review:
        model = await self._get_model(review_id)
        if model is None:
            raise NotFoundError(f"Отзыв {review_id} не найден")
        model.is_hidden = is_hidden
        await self._session.flush()
        return ReviewMapper.to_entity(model)

    async def rating_by_products(
        self, product_ids: list[int]
    ) -> dict[int, ProductRatingAggregate]:
        if not product_ids:
            return {}
        rows = (
            await self._session.execute(
                select(
                    ReviewModel.product_id,
                    func.avg(ReviewModel.rating),
                    func.count(ReviewModel.id),
                )
                .where(
                    ReviewModel.tenant_id == self._tenant,
                    ReviewModel.product_id.in_(product_ids),
                    ReviewModel.is_hidden.is_(False),
                )
                .group_by(ReviewModel.product_id)
            )
        ).all()
        return {
            product_id: ProductRatingAggregate(average_rating=float(avg), reviews_count=count)
            for product_id, avg, count in rows
        }

    async def rating_for_shop(self) -> ProductRatingAggregate:
        row = (
            await self._session.execute(
                select(func.avg(ReviewModel.rating), func.count(ReviewModel.id)).where(
                    ReviewModel.tenant_id == self._tenant,
                    ReviewModel.is_hidden.is_(False),
                )
            )
        ).one()
        avg, count = row
        return ProductRatingAggregate(average_rating=float(avg) if avg is not None else 0.0, reviews_count=count)

    async def _get_model(self, review_id: int) -> ReviewModel | None:
        return (
            await self._session.execute(
                select(ReviewModel).where(
                    ReviewModel.tenant_id == self._tenant,
                    ReviewModel.id == review_id,
                )
            )
        ).scalar_one_or_none()
