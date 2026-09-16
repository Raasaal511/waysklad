from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.common.exceptions import DomainError


@dataclass
class Review:
    """Отзыв покупателя на товар — привязан к принятой заявке с витрины
    (StorefrontRequest в статусе ACCEPTED), один отзыв на заявку. Автор —
    авторизованный Customer, имя берётся из его заявки на момент создания
    (не отдельный логин/профиль)."""

    id: int | None
    tenant_id: int
    product_id: int
    storefront_request_id: int
    customer_id: int
    rating: int
    text: str
    author_name: str
    photo: str = ""
    is_hidden: bool = False  # скрыт владельцем (модерация) — не удалён
    created_at: datetime | None = None

    def validate(self) -> None:
        if not 1 <= self.rating <= 5:
            raise DomainError("Оценка должна быть от 1 до 5")
        if not self.text.strip() and not self.photo:
            raise DomainError("Добавьте текст отзыва или фото")

    def hide(self) -> None:
        self.is_hidden = True

    def unhide(self) -> None:
        self.is_hidden = False
