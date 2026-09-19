from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.domain.reviews.repository import ProductRatingAggregate


@dataclass(frozen=True)
class MarketplaceProductRow:
    """Read-only проекция товара для общего каталога платформы — не Product-сущность,
    т.к. собирается сразу по нескольким tenant и отдаёт только публично безопасные поля."""

    product_id: int
    name: str
    retail_price: Decimal
    photo: str
    category_name: str | None
    in_stock: bool
    min_order_qty: Decimal | None
    order_step_qty: Decimal | None
    shop_slug: str
    shop_name: str
    sku: str
    sold_count: Decimal = Decimal("0")
    rating: ProductRatingAggregate = ProductRatingAggregate(average_rating=0.0, reviews_count=0)
    shop_logo: str = ""
    shop_is_verified: bool = False
    shop_city: str | None = None
    old_price: Decimal | None = None  # уже с учётом «скидка не видна при retail_price > compare_at_price»
    discount_percent: int | None = None  # округление вниз, только при >= 3%
    is_new: bool = False  # created_at за последние 14 дней
    is_hit: bool = False  # топ-10% по sold_count за 30 дней среди видимых товаров платформы, минимум 5 продаж

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "retail_price": str(self.retail_price),
            "photo": self.photo,
            "category_name": self.category_name,
            "in_stock": self.in_stock,
            "min_order_qty": str(self.min_order_qty) if self.min_order_qty is not None else None,
            "order_step_qty": str(self.order_step_qty)
            if self.order_step_qty is not None
            else None,
            "shop_slug": self.shop_slug,
            "shop_name": self.shop_name,
            "sku": self.sku,
            "sold_count": str(self.sold_count),
            "average_rating": self.rating.average_rating,
            "reviews_count": self.rating.reviews_count,
            "shop_logo": self.shop_logo,
            "shop_is_verified": self.shop_is_verified,
            "shop_city": self.shop_city,
            "old_price": str(self.old_price) if self.old_price is not None else None,
            "discount_percent": self.discount_percent,
            "is_new": self.is_new,
            "is_hit": self.is_hit,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MarketplaceProductRow":
        return cls(
            product_id=d["product_id"],
            name=d["name"],
            retail_price=Decimal(d["retail_price"]),
            photo=d["photo"],
            category_name=d["category_name"],
            in_stock=d["in_stock"],
            min_order_qty=Decimal(d["min_order_qty"]) if d["min_order_qty"] is not None else None,
            order_step_qty=Decimal(d["order_step_qty"])
            if d["order_step_qty"] is not None
            else None,
            shop_slug=d["shop_slug"],
            shop_name=d["shop_name"],
            sku=d["sku"],
            sold_count=Decimal(d.get("sold_count", "0")),
            rating=ProductRatingAggregate(
                average_rating=d.get("average_rating", 0.0),
                reviews_count=d.get("reviews_count", 0),
            ),
            shop_logo=d.get("shop_logo", ""),
            shop_is_verified=d.get("shop_is_verified", False),
            shop_city=d.get("shop_city"),
            old_price=Decimal(d["old_price"]) if d.get("old_price") is not None else None,
            discount_percent=d.get("discount_percent"),
            is_new=d.get("is_new", False),
            is_hit=d.get("is_hit", False),
        )


@dataclass(frozen=True)
class ShopChip:
    """Магазин в ряду/списке магазинов маркетплейса (M-B2 п.2, п.3) — не
    Tenant-сущность, публично безопасная read-only проекция."""

    slug: str
    name: str
    logo: str
    city: str | None
    is_verified: bool
    average_rating: float
    reviews_count: int
    products_count: int
    sold_count_30d: Decimal = Decimal("0")  # только для сортировки popular, в ответ API не идёт

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "logo": self.logo,
            "city": self.city,
            "is_verified": self.is_verified,
            "average_rating": self.average_rating,
            "reviews_count": self.reviews_count,
            "products_count": self.products_count,
            "sold_count_30d": str(self.sold_count_30d),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShopChip":
        return cls(
            slug=d["slug"],
            name=d["name"],
            logo=d.get("logo", ""),
            city=d.get("city"),
            is_verified=d.get("is_verified", False),
            average_rating=d.get("average_rating", 0.0),
            reviews_count=d.get("reviews_count", 0),
            products_count=d.get("products_count", 0),
            sold_count_30d=Decimal(d.get("sold_count_30d", "0")),
        )


@dataclass(frozen=True)
class SuggestProductRow:
    """Товар в подсказках поиска (M-B2 п.4) — урезанный набор полей."""

    product_id: int
    name: str
    photo: str
    retail_price: Decimal
    shop_slug: str


class IMarketplaceProductRepository(Protocol):
    """Отдельный от IProductRepository протокол: тот завязан на SqlAlchemyRepository._tenant
    (один tenant на запрос), а общий каталог принципиально читает сразу много tenant."""

    async def list_visible_warehouse_ids(self, tenant_ids: list[int]) -> list[int]:
        """Склады с show_on_storefront=True среди переданных tenant — для расчёта наличия."""
        ...

    async def find_tenant_by_product(self, product_id: int) -> int | None:
        """tenant_id владельца товара — единственный способ узнать, в чей
        tenant-scoped UoW открывать сессию дальше, когда вызывающий знает
        только глобально уникальный product_id, без shop_slug (карточка
        товара маркетплейса, GET /marketplace/products/{id})."""
        ...

    async def get_created_at(self, product_id: int):
        """ProductModel.created_at одного товара — Product (domain-сущность)
        не хранит created_at, поэтому для бейджа «Новинка» на карточке
        товара маркетплейса берём его отдельным точечным запросом."""
        ...

    async def list_products(
        self,
        visible_tenant_ids: list[int],
        warehouse_ids: list[int],
        query: str = "",
        category: str | None = None,
        platform_category_ids: list[int] | None = None,
        city: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        in_stock_only: bool = False,
        with_discount: bool = False,
        variant_size: str | None = None,
        variant_color: str | None = None,
        shop_slug: str | None = None,
        sort: str = "name",
        limit: int = 50,
        offset: int = 0,
        min_rating: int | None = None,
        hit_product_ids: frozenset[int] = frozenset(),
        skip_count: bool = False,
        sold_counts: dict[int, Decimal] | None = None,
        ratings: dict[int, ProductRatingAggregate] | None = None,
    ) -> tuple[list[MarketplaceProductRow], int]:
        """hit_product_ids — предпосчитанный набор «хитов» (см. compute_hit_product_ids),
        нужен только чтобы проставить MarketplaceProductRow.is_hit и для sort='popular'/
        валидации — сам расчёт топ-10% здесь не делается, это отдельный пакетный запрос.

        skip_count=True пропускает COUNT(*)-запрос (total возвращается как -1) —
        для мест, где total не нужен вызывающему (несколько секций главной,
        см. GetMarketplaceHomeUseCase), это лишний запрос на каждую секцию.
        sold_counts/ratings — если переданы, используются вместо собственных
        точечных запросов (чтобы вызывающий мог посчитать их одним batch-запросом
        сразу на все product_id всех секций, а не по одному на секцию)."""
        ...

    async def sold_count_by_products(self, product_ids: list[int]) -> dict[int, Decimal]:
        """Кросс-tenant агрегат — product_id глобально уникален (общий serial PK
        таблицы products), поэтому фильтр по списку id не утекает данные чужого
        tenant без явного tenant_id (тот же принцип, что get_by_token у заявок)."""
        ...

    async def rating_by_products(
        self, product_ids: list[int]
    ) -> dict[int, ProductRatingAggregate]:
        """Кросс-tenant аналог IReviewRepository.rating_by_products — только видимые отзывы."""
        ...

    async def compute_hit_product_ids(self, visible_tenant_ids: list[int]) -> frozenset[int]:
        """Топ-10% по продажам за последние 30 дней среди видимых товаров
        платформы, минимум 5 продаж — пакетный расчёт для бейджа «Хит»
        (см. промпт M-B1 п.5), кешируется вызывающим на 10 минут."""
        ...

    async def count_by_platform_category(
        self, visible_tenant_ids: list[int], city: str | None = None
    ) -> dict[int, int]:
        """Сколько видимых товаров платформы в каждой платформенной категории
        (включая дочерние — считает вызывающий, здесь сырые счётчики по
        Category.platform_category_id) — для GET /marketplace/categories."""
        ...

    async def list_cities(self, visible_tenant_ids: list[int]) -> dict[str, int]:
        """Города магазинов среди видимых tenant -> число магазинов в городе,
        для GET /marketplace/cities."""
        ...

    async def list_shop_chips(
        self,
        visible_tenant_ids: list[int],
        city: str | None = None,
        query: str = "",
        sort: str = "popular",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ShopChip], int]:
        """Магазины с хотя бы одним видимым товаром на витрине — для ряда
        магазинов главной (M-B2 п.2) и GET /marketplace/shops (п.3).
        sort: popular (продажи за 30 дней), rating, new (дата регистрации)."""
        ...

    async def suggest_products(
        self, visible_tenant_ids: list[int], query: str, city: str | None, limit: int = 5
    ) -> list[SuggestProductRow]:
        """ILIKE по названию/артикулу — до limit товаров, для подсказок поиска (M-B2 п.4)."""
        ...

    async def platform_stats(self, visible_tenant_ids: list[int]) -> tuple[int, int]:
        """(products_count, cities_count) среди видимых товаров видимых магазинов —
        для stats в GET /marketplace/home."""
        ...

    async def list_similar_cross_shop(
        self,
        visible_tenant_ids: list[int],
        warehouse_ids: list[int],
        exclude_product_id: int,
        exclude_tenant_id: int,
        category_name: str | None,
        name_words: list[str],
        limit: int,
    ) -> list[MarketplaceProductRow]:
        """Похожие товары ДРУГИХ магазинов платформы (промпт B4 п.2) — текущий
        магазин (exclude_tenant_id) исключён целиком, текущий товар — тоже.
        Сначала — совпадение по названию категории (category_name, как
        category в GET /marketplace/products); если найденных меньше limit —
        добор по похожести названия: pg_trgm similarity(), если расширение
        доступно, иначе ILIKE по name_words (первые два значимых слова
        названия текущего товара, без стоп-слов — считает вызывающий)."""
        ...
