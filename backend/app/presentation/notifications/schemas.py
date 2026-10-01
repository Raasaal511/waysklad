from datetime import datetime

from pydantic import BaseModel, Field

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


class PushKeyResponse(BaseModel):
    # None — push на сервере не настроен, карточку в профиле не показываем
    public_key: str | None


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=200)


class PushSubscriptionRequest(BaseModel):
    """Ровно то, что отдаёт PushSubscription.toJSON() в браузере."""

    endpoint: str = Field(max_length=1024)
    keys: PushSubscriptionKeys


class PushEndpointRequest(BaseModel):
    """Какое устройство — отписать или проверить пробным уведомлением."""

    endpoint: str = Field(max_length=1024)


class PushTestResponse(BaseModel):
    # False — push-сервис не принял (сеть, подписка устарела): кабинет просит
    # проверить интернет, а не делает вид, что всё в порядке
    delivered: bool
