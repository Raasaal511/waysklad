from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base


class FeedbackModel(Base):
    """Обращение из кабинета (вопрос / ошибка / рекомендация) для админки платформы.

    Не TenantMixin: список читает админка поперёк всех магазинов, а tenant_id
    здесь — от кого обращение, не скоуп доступа (как в ErrorLogModel).
    """

    __tablename__ = "feedback"
    __table_args__ = (
        # админка показывает новые сверху, неразобранные — отдельным счётчиком
        Index("ix_feedback_created", "created_at"),
        Index("ix_feedback_resolved", "resolved_at"),
        # лимит частоты: сколько обращений человек отправил за последний час
        Index("ix_feedback_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text, default="")
    photos: Mapped[list[str]] = mapped_column(JSONB, default=list)
    page: Mapped[str] = mapped_column(String(500), default="")
    user_agent: Mapped[str] = mapped_column(String(500), default="")
    app_version: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # «Разобрано» в админке: обращение не удаляется, уходит из новых
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
