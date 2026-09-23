from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.domain.reviews.entities import Review


@dataclass(frozen=True)
class ProductRatingAggregate:
    average_rating: float
    reviews_count: int


@dataclass(frozen=True)
class ReviewTagCount:
    code: str
    count: int


@dataclass(frozen=True)
class ReviewPhotoRef:
    url: str
    review_id: int


@dataclass(frozen=True)
class PublicReviewListFilter:
    """Параметры публичного списка отзывов товара (промпт B3 п.5) — сорт,
    точечные фильтры и пагинация в одном объекте, чтобы не разрастался
    список позиционных аргументов у list_public/count_public."""

    sort: str = "date_desc"  # date_desc | date_asc | rating_desc | rating_asc | useful
    rating: int | None = None
    with_photos: bool = False
    tag: str | None = None
    limit: int = 10
    offset: int = 0


@dataclass(frozen=True)
class PublicReviewListResult:
    reviews: list[Review]
    total: int  # с учётом фильтров (rating/with_photos/tag)
    average_rating: float  # без фильтров — по всем видимым отзывам товара
    reviews_count: int  # без фильтров
    rating_distribution: dict[str, int]  # "5".."1" -> count, без фильтров
    with_photos_count: int  # без фильтров
    tags: list[ReviewTagCount]  # без фильтров, только count > 0, по убыванию
    photos: list[ReviewPhotoRef]  # последние MAX_FEED_PHOTOS фото, без фильтров
    votes: dict[int, tuple[int, int]] = field(default_factory=dict)  # review_id -> (likes, dislikes)


class IReviewRepository(Protocol):
    async def add(self, review: Review) -> Review: ...
    async def get(self, review_id: int) -> Review: ...
    async def get_public(self, review_id: int) -> Review | None:
        """Без tenant-фильтра — только видимый отзыв, по образцу
        tenants.get_by_slug. Нужен, чтобы голосующий покупатель (customer
        JWT, tenant заранее неизвестен) мог найти отзыв и tenant_id для
        открытия tenant-scoped UoW (см. VoteReviewUseCase), не раскрывая
        скрытые отзывы чужой модерации."""
        ...

    async def exists_for_request(self, storefront_request_id: int, product_id: int) -> bool:
        """Уже есть отзыв по этой заявке на ЭТОТ товар — заявка с несколькими
        товарами допускает по отзыву на каждый (промпт B3 п.1)."""
        ...

    async def list_by_product(
        self, product_id: int, *, include_hidden: bool = False
    ) -> list[Review]: ...

    async def list_public(
        self, product_id: int, filters: PublicReviewListFilter
    ) -> PublicReviewListResult:
        """Публичный список с фильтрами/сортировкой + агрегаты одним заходом —
        всё через SQL (не в память), только видимые отзывы (промпт B3 п.5)."""
        ...

    async def list_for_owner(
        self, *, status: str, limit: int, offset: int
    ) -> tuple[list[Review], dict[int, str], int]:
        """Все отзывы магазина (не одного товара) для экрана модерации —
        status: all|visible|hidden. Возвращает (отзывы, {product_id: name},
        total) — имя товара нужно фронту в списке, без второго запроса на
        каждую строку."""
        ...

    async def set_hidden(self, review_id: int, is_hidden: bool) -> Review: ...

    async def rating_by_products(
        self, product_ids: list[int]
    ) -> dict[int, ProductRatingAggregate]:
        """Агрегат (средний рейтинг, число отзывов) только по видимым отзывам,
        для карточек каталога/товара — один запрос на список товаров."""
        ...

    async def rating_for_shop(self) -> ProductRatingAggregate:
        """Агрегат по всем видимым отзывам всех товаров текущего tenant —
        рейтинг магазина целиком (промпт B2 п.2, публичный профиль)."""
        ...


class IReviewUploadRepository(Protocol):
    """Загрузки фото для отзывов (POST /api/reviews/photos) — отдельная
    таблица привязки url -> покупатель, чтобы при создании отзыва проверить,
    что каждый photos[i] загружен именно этим покупателем (промпт B3 п.2)."""

    async def add(self, tenant_id: int | None, customer_id: int, url: str) -> None: ...

    async def count_recent(self, customer_id: int, since: datetime) -> int:
        """Число загрузок покупателя с since — для rate limit 30/час поверх
        уже применённого slowapi (тот лимитирует по IP, не по customer_id;
        см. router)."""
        ...

    async def is_owned_by(self, customer_id: int, url: str) -> bool: ...


class IReviewVoteRepository(Protocol):
    async def set_vote(self, tenant_id: int, review_id: int, customer_id: int, value: int) -> None:
        """value: 1|-1 — upsert; 0 — удаляет голос (снятие)."""
        ...

    async def get_vote(self, review_id: int, customer_id: int) -> int:
        """0, если голоса нет."""
        ...

    async def counts_for_reviews(self, review_ids: list[int]) -> dict[int, tuple[int, int]]:
        """review_id -> (likes, dislikes), одним запросом на список отзывов."""
        ...

    async def my_votes(self, review_ids: list[int], customer_id: int) -> dict[int, int]:
        """review_id -> голос текущего покупателя (только те, где голос есть)."""
        ...
