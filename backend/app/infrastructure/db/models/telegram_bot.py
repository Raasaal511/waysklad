from datetime import datetime

from sqlalchemy import BigInteger, DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base


class TelegramBotSessionModel(Base):
    """Персистентное хранилище FSM-диалога Telegram-бота витрины (aiogram
    BaseStorage) — не мультиарендная таблица (сессия диалога живёт до выбора
    магазина через /start <slug>, tenant_id известен только внутри данных)."""

    __tablename__ = "telegram_bot_sessions"

    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    state: Mapped[str | None] = mapped_column(String(100))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
