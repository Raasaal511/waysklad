from dataclasses import dataclass

from app.domain.common.exceptions import DomainError, NotFoundError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class VoteReviewCommand:
    customer_id: int
    review_id: int
    value: int  # 1 | -1 | 0 (0 снимает голос)


@dataclass(frozen=True)
class VoteReviewResult:
    likes: int
    dislikes: int
    my_vote: int


class VoteReviewUseCase:
    """Покупатель голосует «полезно/не полезно» под отзывом — tenant заранее
    неизвестен (только review_id из customer JWT), поэтому сначала находим
    отзыв публично (см. IReviewRepository.get_public — только видимые, как
    и сам публичный список), затем открываем tenant-scoped UoW тем же
    паттерном, что CreateReviewUseCase резолвит tenant из заявки."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: VoteReviewCommand) -> VoteReviewResult:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            review = await public_uow.reviews.get_public(cmd.review_id)
        if review is None:
            raise NotFoundError("Отзыв не найден")
        if review.customer_id == cmd.customer_id:
            raise DomainError("Нельзя голосовать за свой отзыв")

        async with SqlAlchemyUnitOfWork(review.tenant_id, session_factory=self._session_factory) as uow:
            await uow.review_votes.set_vote(review.tenant_id, cmd.review_id, cmd.customer_id, cmd.value)
            await uow.commit()
            likes, dislikes = (await uow.review_votes.counts_for_reviews([cmd.review_id])).get(
                cmd.review_id, (0, 0)
            )
            return VoteReviewResult(likes=likes, dislikes=dislikes, my_vote=cmd.value)
