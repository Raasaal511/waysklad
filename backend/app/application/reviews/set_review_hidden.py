from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.reviews.entities import Review
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class SetReviewHiddenCommand:
    review_id: int
    is_hidden: bool


class SetReviewHiddenUseCase:
    """Владелец/менеджер скрывает или возвращает неудачный/неадекватный
    отзыв со своей витрины — модерация, не удаление."""

    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

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
            # скрытие/возврат отзыва меняет средний рейтинг товара (каталог,
            # карточка) и магазина целиком (публичный профиль, промпт B2 п.2) —
            # оба закешированы, без явной инвалидации отставали бы до TTL
            await invalidate_shop_cache(self._cache, uow)
            return review
