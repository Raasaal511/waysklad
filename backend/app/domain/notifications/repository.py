from datetime import date
from typing import Protocol

from app.domain.notifications.entities import Notification, NotificationKind


class INotificationRepository(Protocol):
    async def add(self, notification: Notification) -> Notification: ...
    async def get(self, notification_id: int) -> Notification: ...
    async def save(self, notification: Notification) -> Notification: ...

    async def list_for_user(self, user_id: int, limit: int = 30) -> list[Notification]:
        """Последние уведомления пользователя, новые сначала."""
        ...

    async def unread_count(self, user_id: int) -> int: ...
    async def mark_all_read(self, user_id: int) -> int:
        """Возвращает число помеченных прочитанными."""
        ...

    async def exists_for_entity_on(
        self, user_id: int, kind: NotificationKind, entity_id: int, on: date
    ) -> bool:
        """Было ли уже отправлено такое уведомление в этот день — защита от
        повторной рассылки одного и того же долга при ежедневном перезапуске."""
        ...
