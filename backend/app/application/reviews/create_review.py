from dataclasses import dataclass, field

from app.domain.common.cache import ICache
from app.domain.common.exceptions import AccessDeniedError, DomainError, NotFoundError
from app.domain.reviews.entities import Review
from app.domain.storefront.entities import StorefrontRequestStatus
from app.infrastructure.cache.cache_aside import invalidate_shop_cache
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class CreateReviewCommand:
    customer_id: int
    storefront_request_id: int
    product_id: int
    rating: int
    text: str = ""
    photo: str = ""
    photos: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class CreateReviewUseCase:
    """Авторизованный покупатель оставляет отзыв на товар из своей принятой
    (ACCEPTED) заявки с витрины — один отзыв на пару (заявка, товар), заявка
    с несколькими товарами допускает по отзыву на каждый (промпт B3 п.1).
    Автор доказан тем, что заявка с этим customer_id действительно
    принадлежит вызывающему (см. IStorefrontRequestRepository.list_by_customer),
    а не отдельным правом доступа."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def execute(self, cmd: CreateReviewCommand) -> Review:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            my_requests = await public_uow.storefront_requests.list_by_customer(cmd.customer_id)

        request = next((r for r in my_requests if r.id == cmd.storefront_request_id), None)
        if request is None:
            raise NotFoundError("Заявка не найдена")
        if request.status != StorefrontRequestStatus.ACCEPTED:
            raise AccessDeniedError("Отзыв можно оставить только по принятой заявке")
        if not any(line.product_id == cmd.product_id for line in request.lines):
            raise DomainError("Этого товара не было в заявке")

        async with SqlAlchemyUnitOfWork(
            request.tenant_id, session_factory=self._session_factory
        ) as uow:
            if await uow.reviews.exists_for_request(request.id, cmd.product_id):
                raise DomainError("Отзыв на этот товар по этой заявке уже оставлен")

            # каждое фото должно быть загружено ЭТИМ покупателем через
            # POST /api/reviews/photos — иначе кто угодно мог бы подставить
            # чужой/произвольный URL в отзыв (промпт B3 п.2)
            for url in cmd.photos:
                if not await uow.review_uploads.is_owned_by(cmd.customer_id, url):
                    raise DomainError(f"Фото не загружено этим покупателем: {url}")

            review = Review(
                id=None,
                tenant_id=request.tenant_id,
                product_id=cmd.product_id,
                storefront_request_id=request.id,
                customer_id=cmd.customer_id,
                rating=cmd.rating,
                text=cmd.text,
                author_name=request.customer_name,
                photo=cmd.photo,
                photos=list(cmd.photos),
                tags=list(cmd.tags),
            )
            review.normalize_photos()
            review.validate()
            await uow.reviews.add(review)
            await uow.commit()
            # новый отзыв меняет средний рейтинг товара и магазина целиком
            # (публичный профиль, промпт B2 п.2) — оба закешированы
            await invalidate_shop_cache(self._cache, uow)
            return review
