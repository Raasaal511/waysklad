from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base, TenantMixin


class ReviewModel(Base, TenantMixin):
    """Отзыв покупателя на товар — привязан к принятой заявке с витрины,
    уникален по паре (storefront_request_id, product_id): заявка с
    несколькими товарами допускает отзыв на каждый (промпт B3 п.1, было
    unique только по storefront_request_id — баг, чинившийся здесь).

    photos/tags — JSONB (не JSON), т.к. агрегаты публичного списка (счётчик
    тегов, with_photos_count) должны считаться SQL-агрегатами по содержимому
    массива (промпт B3 п.5), а не загрузкой всех отзывов в Python — JSONB
    даёт операторы containment/jsonb_array_elements, обычный json — нет."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("storefront_request_id", "product_id", name="uq_reviews_request_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    storefront_request_id: Mapped[int] = mapped_column(
        ForeignKey("storefront_requests.id"), index=True
    )
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    author_name: Mapped[str] = mapped_column(String(200))
    photo: Mapped[str] = mapped_column(String(500), default="")  # устаревшее, см. photos
    photos: Mapped[list[str]] = mapped_column(JSONB, default=list)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewUploadModel(Base):
    """Фото, загруженное покупателем через POST /api/reviews/photos, ещё до
    (или вместо) создания самого отзыва — отдельная таблица нужна, чтобы при
    POST /api/reviews проверить, что каждый photos[i] действительно загружен
    этим же покупателем, а не подставлен произвольный чужой URL (промпт B3
    п.2). tenant_id nullable: покупатель может загрузить фото до того, как
    известно, в какой отзыв/магазин оно попадёт — привязка только к customer."""

    __tablename__ = "review_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    url: Mapped[str] = mapped_column(String(500), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewVoteModel(Base, TenantMixin):
    """Голос «полезно/не полезно» под отзывом — один голос на покупателя на
    отзыв (см. UniqueConstraint), value переписывается upsert'ом при повторном
    голосовании, а не копится история голосов."""

    __tablename__ = "review_votes"
    __table_args__ = (UniqueConstraint("review_id", "customer_id", name="uq_review_votes_review_customer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    value: Mapped[int] = mapped_column(Integer)  # 1 | -1 (0 не хранится — снятый голос удаляется)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
