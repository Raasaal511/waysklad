from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.reviews.entities import Review


@dataclass(frozen=True)
class ListReviewsForOwnerCommand:
    product_id: int


class ListReviewsForOwnerUseCase:
    """Владелец/менеджер видит ВСЕ отзывы на свой товар, включая скрытые —
    для панели модерации (в отличие от ListProductReviewsUseCase, публичного
    и без скрытых)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ListReviewsForOwnerCommand) -> list[Review]:
        require(actor, Permission.ORDERS_VIEW)

        async with self._uow as uow:
            return await uow.reviews.list_by_product(cmd.product_id, include_hidden=True)
