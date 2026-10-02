from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.notifications.entities import NotificationKind
from app.infrastructure.db.models.base import Base, TenantMixin

NotificationKindColumn = SAEnum(
    NotificationKind, native_enum=False, length=30, values_callable=lambda e: [m.value for m in e]
)


class NotificationModel(Base, TenantMixin):
    """Личное уведомление пользователя — задачу назначили/выполнили и т.п."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread", "tenant_id", "user_id", "is_read"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[NotificationKind] = mapped_column(NotificationKindColumn)
    text: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(200), default="")
    entity_id: Mapped[int | None]
    snapshot_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PushSubscriptionModel(Base, TenantMixin):
    """Подписка браузера на Web Push — см. domain/notifications/push.py."""

    __tablename__ = "push_subscriptions"
    __table_args__ = (Index("ix_push_subscriptions_user", "tenant_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # адрес уникален во всём сервисе: один браузер — одна подписка, кто бы в нём ни вошёл
    endpoint: Mapped[str] = mapped_column(String(1024), unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(200))
    token_version: Mapped[int] = mapped_column(default=0)
    # кабинет подтверждает подписку при каждом открытии — сверх лимита устройств
    # забываем те, что дольше всех не открывали
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
