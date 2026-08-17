from datetime import datetime

from pydantic import BaseModel

from app.domain.notifications.entities import Notification, NotificationKind


class NotificationResponse(BaseModel):
    id: int
    kind: NotificationKind
    text: str
    link: str
    entity_id: int | None
    is_read: bool
    created_at: datetime | None

    @classmethod
    def from_entity(cls, n: Notification) -> "NotificationResponse":
        return cls(
            id=n.id, kind=n.kind, text=n.text, link=n.link,
            entity_id=n.entity_id, is_read=n.is_read, created_at=n.created_at,
        )


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread: int


class MarkAllReadResponse(BaseModel):
    marked: int
