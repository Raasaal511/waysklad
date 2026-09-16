from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base, TenantMixin


class ReviewModel(Base, TenantMixin):
    """Отзыв покупателя на товар — привязан к принятой заявке с витрины,
    один отзыв на заявку (см. IReviewRepository.exists_for_request)."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    storefront_request_id: Mapped[int] = mapped_column(
        ForeignKey("storefront_requests.id"), unique=True, index=True
    )
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    author_name: Mapped[str] = mapped_column(String(200))
    photo: Mapped[str] = mapped_column(String(500), default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
