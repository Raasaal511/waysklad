from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.storefront.entities import MessageAuthor, StorefrontRequestStatus
from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin

StorefrontRequestStatusColumn = SAEnum(
    StorefrontRequestStatus, native_enum=False, length=20,
    values_callable=lambda e: [m.value for m in e],
)
MessageAuthorColumn = SAEnum(
    MessageAuthor, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
)


class StorefrontRequestModel(Base, TenantMixin, TimestampMixin):
    """Сырая заявка с публичной витрины — до принятия владельцем не Order."""

    __tablename__ = "storefront_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(200))
    # None только у заявок до перехода на авторизацию (2026-09-13) — новые
    # заявки требуют авторизованного Customer, см. CreateStorefrontRequestUseCase
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)
    customer_phone: Mapped[str] = mapped_column(String(20), default="")
    customer_telegram_chat_id: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[StorefrontRequestStatus] = mapped_column(
        StorefrontRequestStatusColumn, default=StorefrontRequestStatus.NEW
    )
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    # уникален глобально (не в пределах tenant) — сам по себе служит доказательством
    # владения заявкой, не должен быть угадываем/пересекаться между магазинами
    access_token: Mapped[str] = mapped_column(String(43), unique=True, index=True)
    insufficient_stock_at_request: Mapped[bool] = mapped_column(Boolean, default=False)
    reservation_released: Mapped[bool] = mapped_column(Boolean, default=False)

    lines: Mapped[list["StorefrontRequestLineModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class StorefrontRequestLineModel(Base, TenantMixin):
    __tablename__ = "storefront_request_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    # index: строки всегда читаются пачкой по своей заявке
    request_id: Mapped[int] = mapped_column(
        ForeignKey("storefront_requests.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))


class StorefrontMessageModel(Base, TenantMixin):
    """Сообщение в чате заявки — живёт вместе с заявкой, не отдельная сущность."""

    __tablename__ = "storefront_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("storefront_requests.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[MessageAuthor] = mapped_column(MessageAuthorColumn)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductViewDailyModel(Base, TenantMixin):
    """Просмотры карточки товара, агрегированные по дню — сырые события
    (кто, когда, с какого IP) не храним, см. промпт B1 п.5: дедупликация
    делается на уровне Redis-ключа до инкремента этого счётчика."""

    __tablename__ = "product_view_daily"
    __table_args__ = (UniqueConstraint("tenant_id", "product_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)
