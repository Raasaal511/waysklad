import json
from datetime import datetime

from sqlalchemy import and_, case, cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB

from app.domain.common.exceptions import NotFoundError
from app.domain.reviews.entities import Review
from app.domain.reviews.repository import (
    IReviewRepository,
    IReviewUploadRepository,
    IReviewVoteRepository,
    ProductRatingAggregate,
    PublicReviewListFilter,
    PublicReviewListResult,
    ReviewPhotoRef,
    ReviewTagCount,
)
from app.infrastructure.db.mappers.reviews import ReviewMapper
from app.infrastructure.db.models.catalog import ProductModel
from app.infrastructure.db.models.reviews import ReviewModel, ReviewUploadModel, ReviewVoteModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository

_MAX_FEED_PHOTOS = 30

# jsonb_array_length(NULL) падает, а старые строки могли быть заведены с NULL
# (default=list применяется только на INSERT через ORM, не на существующих
# строках) — coalesce к пустому массиву перед любой jsonb-функцией.
_PHOTOS = func.coalesce(ReviewModel.photos, cast(literal("[]"), JSONB))
_TAGS = func.coalesce(ReviewModel.tags, cast(literal("[]"), JSONB))
_HAS_PHOTOS = func.jsonb_array_length(_PHOTOS) > 0


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

    async def get_public(self, review_id: int) -> Review | None:
        model = (
            await self._session.execute(
                select(ReviewModel).where(
                    ReviewModel.id == review_id, ReviewModel.is_hidden.is_(False)
                )
            )
        ).scalar_one_or_none()
        return ReviewMapper.to_entity(model) if model is not None else None

    async def exists_for_request(self, storefront_request_id: int, product_id: int) -> bool:
        result = await self._session.execute(
            select(ReviewModel.id).where(
                ReviewModel.storefront_request_id == storefront_request_id,
                ReviewModel.product_id == product_id,
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

    async def list_public(
        self, product_id: int, filters: PublicReviewListFilter
    ) -> PublicReviewListResult:
        visible = and_(
            ReviewModel.tenant_id == self._tenant,
            ReviewModel.product_id == product_id,
            ReviewModel.is_hidden.is_(False),
        )

        # Агрегаты "без фильтров" — по всем видимым отзывам товара, отдельный
        # запрос от отфильтрованного списка (промпт B3 п.5: average_rating/
        # reviews_count/rating_distribution/with_photos_count не зависят от
        # rating/with_photos/tag, иначе гистограмма "подстраивалась" бы под
        # собственный фильтр и не позволяла бы сравнить его с целым).
        agg_row = (
            await self._session.execute(
                select(
                    func.avg(ReviewModel.rating),
                    func.count(ReviewModel.id),
                    func.count(ReviewModel.id).filter(ReviewModel.rating == 5),
                    func.count(ReviewModel.id).filter(ReviewModel.rating == 4),
                    func.count(ReviewModel.id).filter(ReviewModel.rating == 3),
                    func.count(ReviewModel.id).filter(ReviewModel.rating == 2),
                    func.count(ReviewModel.id).filter(ReviewModel.rating == 1),
                    func.count(ReviewModel.id).filter(_HAS_PHOTOS),
                ).where(visible)
            )
        ).one()
        avg, total_count, c5, c4, c3, c2, c1, with_photos_count = agg_row
        average_rating = float(avg) if avg is not None else 0.0
        rating_distribution = {"5": c5, "4": c4, "3": c3, "2": c2, "1": c1}

        tags = await self._tag_counts(visible)
        photos = await self._recent_photos(visible)

        # Список: применяем rating/with_photos/tag поверх того же visible.
        conditions = [visible]
        if filters.rating is not None:
            conditions.append(ReviewModel.rating == filters.rating)
        if filters.with_photos:
            conditions.append(_HAS_PHOTOS)
        if filters.tag is not None:
            # cast(literal(python_list), JSONB) шлёт сырой список параметром —
            # psycopg не сериализует его в JSON-текст сам, поэтому явный
            # json.dumps перед cast (проверено отдельным запросом к БД).
            conditions.append(_TAGS.op("@>")(cast(literal(json.dumps([filters.tag])), JSONB)))
        where_clause = and_(*conditions)

        filtered_total = (
            await self._session.execute(select(func.count(ReviewModel.id)).where(where_clause))
        ).scalar_one()

        order_by = self._order_by(filters.sort)
        stmt = select(ReviewModel).where(where_clause).order_by(*order_by).limit(filters.limit).offset(
            filters.offset
        )
        # "useful" сортирует по (likes - dislikes) — считаем через LEFT JOIN
        # на review_votes прямо в этом запросе, не отдельным проходом.
        if filters.sort == "useful":
            likes_minus_dislikes = func.coalesce(
                func.sum(case((ReviewVoteModel.value == 1, 1), else_=0))
                - func.sum(case((ReviewVoteModel.value == -1, 1), else_=0)),
                0,
            )
            stmt = (
                select(ReviewModel)
                .outerjoin(ReviewVoteModel, ReviewVoteModel.review_id == ReviewModel.id)
                .where(where_clause)
                .group_by(ReviewModel.id)
                .order_by(likes_minus_dislikes.desc(), ReviewModel.created_at.desc())
                .limit(filters.limit)
                .offset(filters.offset)
            )

        models = (await self._session.execute(stmt)).scalars().all()
        reviews = [ReviewMapper.to_entity(m) for m in models]

        votes = await self._votes_for(reviews)

        return PublicReviewListResult(
            reviews=reviews,
            total=filtered_total,
            average_rating=average_rating,
            reviews_count=total_count,
            rating_distribution=rating_distribution,
            with_photos_count=with_photos_count,
            tags=tags,
            photos=photos,
            votes=votes,
        )

    async def _votes_for(self, reviews: list[Review]) -> dict[int, tuple[int, int]]:
        if not reviews:
            return {}
        ids = [r.id for r in reviews if r.id is not None]
        rows = (
            await self._session.execute(
                select(
                    ReviewVoteModel.review_id,
                    func.count(ReviewVoteModel.id).filter(ReviewVoteModel.value == 1),
                    func.count(ReviewVoteModel.id).filter(ReviewVoteModel.value == -1),
                )
                .where(ReviewVoteModel.review_id.in_(ids))
                .group_by(ReviewVoteModel.review_id)
            )
        ).all()
        return {review_id: (likes, dislikes) for review_id, likes, dislikes in rows}

    @staticmethod
    def _order_by(sort: str):
        if sort == "date_asc":
            return (ReviewModel.created_at.asc(),)
        if sort == "rating_desc":
            return (ReviewModel.rating.desc(), ReviewModel.created_at.desc())
        if sort == "rating_asc":
            return (ReviewModel.rating.asc(), ReviewModel.created_at.desc())
        # "useful" собирается отдельным stmt в list_public (нужен JOIN) —
        # сюда не попадает, но возвращаем дефолт на случай неизвестного sort
        # (роутер уже валидирует Literal, это подстраховка на уровне репо).
        return (ReviewModel.created_at.desc(),)

    async def _tag_counts(self, visible) -> list[ReviewTagCount]:
        # jsonb_array_elements_text разворачивает массив тегов каждого отзыва
        # в строки — считаем по товару одним GROUP BY, без данных в память.
        tag_expr = func.jsonb_array_elements_text(_TAGS).table_valued("value")
        stmt = (
            select(tag_expr.c.value, func.count().label("cnt"))
            .select_from(ReviewModel)
            .join(tag_expr, literal(True))
            .where(visible)
            .group_by(tag_expr.c.value)
            .order_by(func.count().desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [ReviewTagCount(code=code, count=count) for code, count in rows]

    async def _recent_photos(self, visible) -> list[ReviewPhotoRef]:
        photo_expr = func.jsonb_array_elements_text(_PHOTOS).table_valued("value")
        stmt = (
            select(photo_expr.c.value, ReviewModel.id, ReviewModel.created_at)
            .select_from(ReviewModel)
            .join(photo_expr, literal(True))
            .where(visible)
            .order_by(ReviewModel.created_at.desc())
            .limit(_MAX_FEED_PHOTOS)
        )
        rows = (await self._session.execute(stmt)).all()
        return [ReviewPhotoRef(url=url, review_id=review_id) for url, review_id, _ in rows]

    async def list_for_owner(
        self, *, status: str, limit: int, offset: int
    ) -> tuple[list[Review], dict[int, str], int]:
        conditions = [ReviewModel.tenant_id == self._tenant]
        if status == "visible":
            conditions.append(ReviewModel.is_hidden.is_(False))
        elif status == "hidden":
            conditions.append(ReviewModel.is_hidden.is_(True))
        where_clause = and_(*conditions)

        total = (
            await self._session.execute(select(func.count(ReviewModel.id)).where(where_clause))
        ).scalar_one()

        models = (
            await self._session.execute(
                select(ReviewModel)
                .where(where_clause)
                .order_by(ReviewModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        reviews = [ReviewMapper.to_entity(m) for m in models]

        product_ids = {r.product_id for r in reviews}
        names: dict[int, str] = {}
        if product_ids:
            rows = (
                await self._session.execute(
                    select(ProductModel.id, ProductModel.name).where(
                        ProductModel.tenant_id == self._tenant, ProductModel.id.in_(product_ids)
                    )
                )
            ).all()
            names = dict(rows)

        return reviews, names, total

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


class SqlAlchemyReviewUploadRepository(SqlAlchemyRepository, IReviewUploadRepository):
    async def add(self, tenant_id: int | None, customer_id: int, url: str) -> None:
        self._session.add(ReviewUploadModel(tenant_id=tenant_id, customer_id=customer_id, url=url))
        await self._session.flush()

    async def count_recent(self, customer_id: int, since: datetime) -> int:
        return (
            await self._session.execute(
                select(func.count(ReviewUploadModel.id)).where(
                    ReviewUploadModel.customer_id == customer_id,
                    ReviewUploadModel.created_at >= since,
                )
            )
        ).scalar_one()

    async def is_owned_by(self, customer_id: int, url: str) -> bool:
        result = await self._session.execute(
            select(ReviewUploadModel.id).where(
                ReviewUploadModel.customer_id == customer_id, ReviewUploadModel.url == url
            )
        )
        return result.scalar_one_or_none() is not None


class SqlAlchemyReviewVoteRepository(SqlAlchemyRepository, IReviewVoteRepository):
    async def set_vote(self, tenant_id: int, review_id: int, customer_id: int, value: int) -> None:
        existing = (
            await self._session.execute(
                select(ReviewVoteModel).where(
                    ReviewVoteModel.review_id == review_id, ReviewVoteModel.customer_id == customer_id
                )
            )
        ).scalar_one_or_none()

        if value == 0:
            if existing is not None:
                await self._session.delete(existing)
                await self._session.flush()
            return

        if existing is not None:
            existing.value = value
        else:
            self._session.add(
                ReviewVoteModel(
                    tenant_id=tenant_id, review_id=review_id, customer_id=customer_id, value=value
                )
            )
        await self._session.flush()

    async def get_vote(self, review_id: int, customer_id: int) -> int:
        result = await self._session.execute(
            select(ReviewVoteModel.value).where(
                ReviewVoteModel.review_id == review_id, ReviewVoteModel.customer_id == customer_id
            )
        )
        value = result.scalar_one_or_none()
        return value if value is not None else 0

    async def counts_for_reviews(self, review_ids: list[int]) -> dict[int, tuple[int, int]]:
        if not review_ids:
            return {}
        rows = (
            await self._session.execute(
                select(
                    ReviewVoteModel.review_id,
                    func.count(ReviewVoteModel.id).filter(ReviewVoteModel.value == 1),
                    func.count(ReviewVoteModel.id).filter(ReviewVoteModel.value == -1),
                )
                .where(ReviewVoteModel.review_id.in_(review_ids))
                .group_by(ReviewVoteModel.review_id)
            )
        ).all()
        return {review_id: (likes, dislikes) for review_id, likes, dislikes in rows}

    async def my_votes(self, review_ids: list[int], customer_id: int) -> dict[int, int]:
        if not review_ids:
            return {}
        rows = (
            await self._session.execute(
                select(ReviewVoteModel.review_id, ReviewVoteModel.value).where(
                    ReviewVoteModel.review_id.in_(review_ids),
                    ReviewVoteModel.customer_id == customer_id,
                )
            )
        ).all()
        return dict(rows)
