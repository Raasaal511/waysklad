from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, func
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
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
