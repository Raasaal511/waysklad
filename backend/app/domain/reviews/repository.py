from dataclasses import dataclass
from typing import Protocol

from app.domain.reviews.entities import Review


@dataclass(frozen=True)
class ProductRatingAggregate:
    average_rating: float
    reviews_count: int


class IReviewRepository(Protocol):
    async def add(self, review: Review) -> Review: ...
    async def get(self, review_id: int) -> Review: ...
    async def exists_for_request(self, storefront_request_id: int) -> bool:
        """Уже есть отзыв по этой заявке — один отзыв на заявку."""
        ...

    async def list_by_product(
        self, product_id: int, *, include_hidden: bool = False
    ) -> list[Review]: ...

    async def set_hidden(self, review_id: int, is_hidden: bool) -> Review: ...

    async def rating_by_products(
        self, product_ids: list[int]
    ) -> dict[int, ProductRatingAggregate]:
        """Агрегат (средний рейтинг, число отзывов) только по видимым отзывам,
        для карточек каталога/товара — один запрос на список товаров."""
        ...
