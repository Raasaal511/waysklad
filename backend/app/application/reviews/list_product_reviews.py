from dataclasses import dataclass

from app.domain.reviews.repository import PublicReviewListFilter, PublicReviewListResult
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class ListProductReviewsCommand:
    slug: str
    product_id: int
    filters: PublicReviewListFilter
    customer_id: int | None = None  # из необязательного customer JWT — для my_vote


@dataclass(frozen=True)
class ProductReviewsResult:
    list_result: PublicReviewListResult
    my_votes: dict[int, int]  # review_id -> голос текущего покупателя (пусто без токена)


class ListProductReviewsUseCase:
    """Публичный (без авторизации) список видимых отзывов на товар — для
    карточки товара на витрине. Скрытые владельцем (is_hidden) не отдаются
    и не входят в агрегаты. Фильтры/сортировка/пагинация — промпт B3 п.5."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: ListProductReviewsCommand) -> ProductReviewsResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return None

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            result = await uow.reviews.list_public(cmd.product_id, cmd.filters)
            my_votes: dict[int, int] = {}
            if cmd.customer_id is not None:
                review_ids = [r.id for r in result.reviews if r.id is not None]
                my_votes = await uow.review_votes.my_votes(review_ids, cmd.customer_id)

        return ProductReviewsResult(list_result=result, my_votes=my_votes)
