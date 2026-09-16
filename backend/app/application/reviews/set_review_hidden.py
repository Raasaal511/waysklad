from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.reviews.entities import Review


@dataclass(frozen=True)
class SetReviewHiddenCommand:
    review_id: int
    is_hidden: bool


class SetReviewHiddenUseCase:
    """Владелец/менеджер скрывает или возвращает неудачный/неадекватный
    отзыв со своей витрины — модерация, не удаление."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: SetReviewHiddenCommand) -> Review:
        require(actor, Permission.ORDERS_MANAGE)

        async with self._uow as uow:
            review = await uow.reviews.set_hidden(cmd.review_id, cmd.is_hidden)
            await uow.audit.add(
                AuditEntry.record(
                    actor,
                    "review.hide" if cmd.is_hidden else "review.unhide",
                    review.id,
                )
            )
            await uow.commit()
            return review
