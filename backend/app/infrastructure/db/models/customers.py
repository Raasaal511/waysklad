from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
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
    phone_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    personal_data_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class CustomerPhoneChangeModel(Base):
    """Заявка на смену номера. Короткоживущая, как и ссылка входа, поэтому
    без TimestampMixin: created_at здесь смысловое поле домена."""

    __tablename__ = "customer_phone_changes"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    new_phone: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CustomerPhoneCodeModel(Base):
    """Код подтверждения телефона. created_at здесь смысловое поле (по нему
    считается лимит «не больше N в час»), поэтому без TimestampMixin — как и
    у CustomerLoginLinkModel."""

    __tablename__ = "customer_phone_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    phone: Mapped[str] = mapped_column(String(20))
    code_hash: Mapped[str] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_via: Mapped[str] = mapped_column(String(16), default="", server_default="")

    # «сколько кодов выпущено за последний час этому покупателю» — самый
    # частый запрос к таблице (лимит перед каждой отправкой)
    __table_args__ = (Index("ix_customer_phone_codes_customer_created", "customer_id", "created_at"),)
