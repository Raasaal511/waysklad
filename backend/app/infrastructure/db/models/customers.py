from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base, TimestampMixin


class CustomerModel(Base, TimestampMixin):
    """Аккаунт покупателя — общий на платформу, не привязан к tenant (тот же
    паттерн верхнеуровневой сущности, что и TenantModel)."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(32), default="")
    # "" — аккаунт заведён входом через Telegram-бота, без регистрации по паролю.
    # Уникальность частичным индексом: пустых username может быть сколько угодно
    # (см. миграцию 2026-09-21_customer_password_hash).
    username: Mapped[str] = mapped_column(String(32), default="", server_default="", index=True)
    password_hash: Mapped[str] = mapped_column(String(128), default="", server_default="")
    token_version: Mapped[int] = mapped_column(Integer, default=0)


class CustomerLoginLinkModel(Base):
    """Одноразовая ссылка входа — короткоживущая (LOGIN_LINK_TTL), без
    TimestampMixin: created_at здесь смысловое поле домена, не служебное."""

    __tablename__ = "customer_login_links"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # непустые только у ссылок регистрации (см. CustomerLoginLink.is_registration)
    username: Mapped[str] = mapped_column(String(32), default="", server_default="")
    password_hash: Mapped[str] = mapped_column(String(128), default="", server_default="")
