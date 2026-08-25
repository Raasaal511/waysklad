from app.domain.common.exceptions import AccessDeniedError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.domain.notifications.entities import Notification


class MarkNotificationReadUseCase:
    """Уведомления личные — права не нужны, только принадлежность актору."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, notification_id: int) -> Notification:
        async with self._uow as uow:
            notification = await uow.notifications.get(notification_id)
            if notification.user_id != actor.id:
                raise AccessDeniedError("Это уведомление не ваше")
            notification.mark_read()
            notification = await uow.notifications.save(notification)
            await uow.commit()
            return notification


class MarkAllNotificationsReadUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> int:
        async with self._uow as uow:
            count = await uow.notifications.mark_all_read(actor.id)
            await uow.commit()
            return count
