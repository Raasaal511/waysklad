from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.common.exceptions import DomainError
from app.domain.reviews.tags import REVIEW_TAG_CODES

MAX_PHOTOS = 5
MAX_TAGS = 5


@dataclass
class Review:
    """Отзыв покупателя на товар — привязан к паре (заявка, товар): один
    отзыв на товар в рамках заявки (заявка с несколькими товарами допускает
    отзыв на каждый, см. IReviewRepository.exists_for_request — промпт B3
    п.1, было привязано только к заявке целиком, это баг). Автор —
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
    photo: str = ""  # устаревшее одиночное фото — оставлено для совместимости, см. photos
    photos: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # коды из REVIEW_TAG_CODES
    is_hidden: bool = False  # скрыт владельцем (модерация) — не удалён
    created_at: datetime | None = None

    def validate(self) -> None:
        if not 1 <= self.rating <= 5:
            raise DomainError("Оценка должна быть от 1 до 5")
        if not self.text.strip() and not self.photo and not self.photos:
            raise DomainError("Добавьте текст отзыва или фото")
        if len(self.photos) > MAX_PHOTOS:
            raise DomainError(f"Не более {MAX_PHOTOS} фото в отзыве")
        if len(self.tags) > MAX_TAGS:
            raise DomainError(f"Не более {MAX_TAGS} тегов в отзыве")
        unknown = set(self.tags) - REVIEW_TAG_CODES
        if unknown:
            raise DomainError(f"Неизвестный тег: {', '.join(sorted(unknown))}")

    def hide(self) -> None:
        self.is_hidden = True

    def unhide(self) -> None:
        self.is_hidden = False

    def normalize_photos(self) -> None:
        """photos = [photo], если photos пуст, а photo задано (совместимость
        со старыми записями/клиентами, см. промпт B3 п.2) — вызывается и на
        чтении из БД, и после создания, чтобы photo/photos были согласованы
        независимо от того, каким полем пришли данные."""
        if not self.photos and self.photo:
            self.photos = [self.photo]
        self.photo = self.photos[0] if self.photos else ""
