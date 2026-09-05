from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.notifications.entities import Notification


@dataclass(frozen=True)
class ListNotificationsResult:
    items: list[Notification]
    unread: int


class ListNotificationsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> ListNotificationsResult:
        async with self._uow as uow:
            items = await uow.notifications.list_for_user(actor.id)
            unread = await uow.notifications.unread_count(actor.id)
            return ListNotificationsResult(items=items, unread=unread)
