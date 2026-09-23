from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from app.application.marketplace.hit_products import get_hit_product_ids
from app.domain.common.cache import ICache
from app.domain.marketplace.repository import MarketplaceProductRow, ShopChip
from app.domain.platform.banners import PlatformBanner
from app.domain.platform.entities import PlatformCategory
from app.domain.reviews.repository import ProductRatingAggregate
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_EMPTY_RATING = ProductRatingAggregate(average_rating=0.0, reviews_count=0)

_CACHE_TTL_SECONDS = 60  # 60 с на город (M-B2 п.2)

_SECTION_SIZE = 10
_SECTION_MIN_PRODUCTS = 5
_MAX_PER_SHOP_IN_SECTION = 3
_CATEGORIES_LIMIT = 12
_SHOPS_LIMIT = 20
_TOP_RATED_MIN_REVIEWS = 3
_TOP_RATED_MIN_RATING = 4.5
# запас над _SECTION_SIZE, с которым тянем товары из БД перед жадным отбором
# «не больше 3 на магазин» — без этого секция могла бы недобрать 10 штук,
# если среди первых 10 по сортировке у одного магазина оказалось 4+ товаров
_SECTION_FETCH_LIMIT = 60


@dataclass(frozen=True)
class GetHomeCommand:
    city: str | None = None


@dataclass(frozen=True)
class HomeSection:
    key: str
    title: str
    products: list[MarketplaceProductRow]


@dataclass(frozen=True)
class HomeStats:
    shops_count: int
    products_count: int
    cities_count: int


@dataclass(frozen=True)
class GetHomeResult:
    hero_banners: list[PlatformBanner]
    promo_banners: list[PlatformBanner]
    categories: list[PlatformCategory]
    category_products_counts: dict[int, int]
    shops: list[ShopChip]
    sections: list[HomeSection]
    stats: HomeStats

    def to_json(self) -> dict:
        return {
            "hero_banners": [b.to_dict() for b in self.hero_banners],
            "promo_banners": [b.to_dict() for b in self.promo_banners],
            "categories": [c.to_dict() for c in self.categories],
            "category_products_counts": {
                str(k): v for k, v in self.category_products_counts.items()
            },
            "shops": [s.to_dict() for s in self.shops],
            "sections": [
                {
                    "key": s.key,
                    "title": s.title,
                    "products": [p.to_dict() for p in s.products],
                }
                for s in self.sections
            ],
            "stats": {
                "shops_count": self.stats.shops_count,
                "products_count": self.stats.products_count,
                "cities_count": self.stats.cities_count,
            },
        }

    @classmethod
    def from_json(cls, d: dict) -> "GetHomeResult":
        return cls(
            hero_banners=[PlatformBanner.from_dict(b) for b in d["hero_banners"]],
            promo_banners=[PlatformBanner.from_dict(b) for b in d["promo_banners"]],
            categories=[PlatformCategory.from_dict(c) for c in d["categories"]],
            category_products_counts={
                int(k): v for k, v in d["category_products_counts"].items()
            },
            shops=[ShopChip.from_dict(s) for s in d["shops"]],
            sections=[
                HomeSection(
                    key=s["key"], title=s["title"],
                    products=[MarketplaceProductRow.from_dict(p) for p in s["products"]],
                )
                for s in d["sections"]
            ],
            stats=HomeStats(**d["stats"]),
        )


def _with_sold_and_rating(
    row: MarketplaceProductRow,
    sold_counts: dict[int, Decimal],
    ratings: dict[int, ProductRatingAggregate],
) -> MarketplaceProductRow:
    """list_products() был вызван с sold_counts={}/ratings={} (см. вызов ниже) —
    оба поля row ещё нулевые, здесь подставляем batch-посчитанные значения
    (один запрос на все 4 секции сразу, а не по одному на секцию)."""
    return replace(
        row,
        sold_count=sold_counts.get(row.product_id, Decimal("0")),
        rating=ratings.get(row.product_id, _EMPTY_RATING),
    )


def _greedy_limit_per_shop(
    rows: list[MarketplaceProductRow], size: int, max_per_shop: int
) -> list[MarketplaceProductRow]:
    """Жадный отбор по порядку сортировки: пропускает товар, если у его
    магазина уже набралось max_per_shop штук в результате (см. промпт M-B2
    п.2 — «разнообразие»). Порядок сортировки, уже применённый в SQL,
    сохраняется."""
    counts: dict[str, int] = {}
    result: list[MarketplaceProductRow] = []
    for row in rows:
        if len(result) >= size:
            break
        if counts.get(row.shop_slug, 0) >= max_per_shop:
            continue
        counts[row.shop_slug] = counts.get(row.shop_slug, 0) + 1
        result.append(row)
    return result


class GetMarketplaceHomeUseCase:
    """Все данные главной маркетплейса одним публичным запросом — баннеры,
    категории с товарами, ряд магазинов, товарные секции и статистика платформы
    (см. промпт M-B2 п.2). Кешируется на 60 секунд на город: тяжёлый агрегат
    по всей платформе, собирается пакетными запросами, без N+1 по товарам/магазинам."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def execute(self, cmd: GetHomeCommand) -> GetHomeResult:
        return await self._cached_execute(cmd)

    async def _execute_uncached(self, cmd: GetHomeCommand) -> GetHomeResult:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            all_tenants = await uow.tenants.list_all()
            visible_tenants = [
                t for t in all_tenants if t.storefront_enabled and not t.is_suspended
            ]
            visible_tenant_ids = [t.id for t in visible_tenants]

            today = date.today()
            hero_banners = await uow.platform_banners.list_live(today, cmd.city)
            promo_banners = [b for b in hero_banners if b.placement == "promo"]
            hero_banners = [b for b in hero_banners if b.placement == "hero"]

            if not visible_tenant_ids:
                empty_stats = HomeStats(shops_count=0, products_count=0, cities_count=0)
                return GetHomeResult(
                    hero_banners=hero_banners, promo_banners=promo_banners,
                    categories=[], category_products_counts={}, shops=[],
                    sections=[], stats=empty_stats,
                )

            all_categories = await uow.platform_categories.list_active()
            category_counts = await uow.marketplace_products.count_by_platform_category(
                visible_tenant_ids, city=cmd.city
            )
            categories = sorted(
                (c for c in all_categories if category_counts.get(c.id)),
                key=lambda c: c.sort_order,
            )[:_CATEGORIES_LIMIT]

            shops, shops_total = await uow.marketplace_products.list_shop_chips(
                visible_tenant_ids, city=cmd.city, sort="popular", limit=_SHOPS_LIMIT
            )
            # порядок «проверенные → с лого → по продажам» (M-B2 п.2): list_shop_chips
            # уже отсортировал по продажам за 30 дней, здесь только переставляем
            # по двум дополнительным булевым признакам, sort стабилен — порядок продаж
            # внутри одинаковых (is_verified, has_logo) сохраняется
            shops = sorted(shops, key=lambda s: (not s.is_verified, not bool(s.logo)))

            warehouse_ids = await uow.marketplace_products.list_visible_warehouse_ids(
                visible_tenant_ids
            )
            hit_product_ids = await get_hit_product_ids(uow, self._cache, visible_tenant_ids)

            # Первый проход — сырые ряды каждой секции БЕЗ sold_count/rating
            # (skip_count=True тоже экономит COUNT(*) на каждую секцию, total
            # секциям не нужен). sold_count/rating считаются один раз на
            # ВСЕ секции сразу вторым проходом ниже — иначе на каждую из 4
            # секций ушло бы по 2 своих batch-запроса (см. промпт M-B2 п.2,
            # тест на число SQL-запросов).
            section_specs = [
                ("discount", "Скидки", {"with_discount": True, "sort": "discount"}),
                ("popular", "Хиты продаж", {"sort": "popular"}),
                ("new", "Новинки", {"sort": "created_desc"}),
                ("top_rated", "С высоким рейтингом", {"sort": "rating"}),
            ]
            raw_sections: list[tuple[str, str, list[MarketplaceProductRow]]] = []
            for key, title, extra_params in section_specs:
                rows, _total = await uow.marketplace_products.list_products(
                    visible_tenant_ids=visible_tenant_ids,
                    warehouse_ids=warehouse_ids,
                    city=cmd.city,
                    in_stock_only=True,
                    limit=_SECTION_FETCH_LIMIT,
                    hit_product_ids=hit_product_ids,
                    skip_count=True,
                    sold_counts={},
                    ratings={},
                    **extra_params,
                )
                raw_sections.append((key, title, rows))

            all_product_ids = list(
                {row.product_id for _, _, rows in raw_sections for row in rows}
            )
            sold_counts = await uow.marketplace_products.sold_count_by_products(all_product_ids)
            ratings = await uow.marketplace_products.rating_by_products(all_product_ids)

            sections: list[HomeSection] = []
            for key, title, rows in raw_sections:
                enriched = [_with_sold_and_rating(row, sold_counts, ratings) for row in rows]
                if key == "top_rated":
                    # рейтинг в list_products при skip_count/ratings={} не считается —
                    # фильтруем здесь, уже на обогащённых рядах (M-B2 п.2: порог
                    # top_rated — reviews_count >= 3 и рейтинг >= 4.5, не целое
                    # число звёзд, поэтому не через min_rating в SQL)
                    enriched = [
                        r for r in enriched
                        if r.rating.reviews_count >= _TOP_RATED_MIN_REVIEWS
                        and r.rating.average_rating >= _TOP_RATED_MIN_RATING
                    ]
                    enriched.sort(
                        key=lambda r: (r.rating.average_rating, r.rating.reviews_count),
                        reverse=True,
                    )
                selected = _greedy_limit_per_shop(enriched, _SECTION_SIZE, _MAX_PER_SHOP_IN_SECTION)
                if len(selected) < _SECTION_MIN_PRODUCTS:
                    continue
                sections.append(HomeSection(key=key, title=title, products=selected))

            products_count, cities_count = await uow.marketplace_products.platform_stats(
                visible_tenant_ids
            )
            stats = HomeStats(
                shops_count=shops_total, products_count=products_count, cities_count=cities_count
            )

        return GetHomeResult(
            hero_banners=hero_banners,
            promo_banners=promo_banners,
            categories=categories,
            category_products_counts=category_counts,
            shops=shops,
            sections=sections,
            stats=stats,
        )

    _cached_execute = cached_use_case(
        "marketplace_home",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=GetHomeResult.from_json,
    )(_execute_uncached)
