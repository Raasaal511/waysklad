from dataclasses import dataclass
from typing import Literal

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.reviews.entities import Review

ReviewStatusFilter = Literal["all", "visible", "hidden"]


@dataclass(frozen=True)
class ListAllReviewsForOwnerCommand:
    status: ReviewStatusFilter = "all"
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class AllReviewsForOwnerResult:
    reviews: list[Review]
    product_names: dict[int, str]  # product_id -> name, для карточки в списке модерации
    total: int


class ListAllReviewsForOwnerUseCase:
    """Все отзывы магазина (по всем товарам, не одному) — экран модерации
    целиком, а не по карточке отдельного товара (промпт B3 п.7, в отличие от
    ListReviewsForOwnerUseCase)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(
        self, actor: Actor, cmd: ListAllReviewsForOwnerCommand
    ) -> AllReviewsForOwnerResult:
        require(actor, Permission.ORDERS_VIEW)

        async with self._uow as uow:
            reviews, names, total = await uow.reviews.list_for_owner(
                status=cmd.status, limit=cmd.limit, offset=cmd.offset
            )
        return AllReviewsForOwnerResult(reviews=reviews, product_names=names, total=total)
