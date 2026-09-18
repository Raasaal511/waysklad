from dataclasses import dataclass
from decimal import Decimal

from app.domain.catalog.entities import Category, Product
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.identity.entities import Warehouse
from app.domain.reviews.repository import ProductRatingAggregate
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 20

# покупателю доступна только эта часть сортировок ProductFilterFactory —
# ни margin (закупочная маржа), ни stock (точный остаток) публично не отдаются
_SORT_ALIASES = {
    "name": "name",
    "price_asc": "retail_price",
    "price_desc": "-retail_price",
    "created_desc": "-created_at",
    "popular": "-sold_count_30d",
    "rating": "-average_rating",
    "discount": "-discount_percent",
}


@dataclass(frozen=True)
class GetStorefrontCatalogCommand:
    slug: str
    query: str = ""
    limit: int = 50
    offset: int = 0
    category_id: int | None = None
    warehouse_id: int | None = None  # витрина одного склада — наличие считается только по нему
    sort: str = "name"  # name, price_asc, price_desc, created_desc
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock_only: bool = False
    with_discount: bool = False
    variant_size: str | None = None
    variant_color: str | None = None
    min_rating: int | None = None  # 1..5 — «от N звёзд», товар без отзывов не проходит


@dataclass(frozen=True)
class StorefrontCategoryCount:
    category: Category
    product_count: int


@dataclass(frozen=True)
class StorefrontCatalogResult:
    shop_name: str
    products: list[Product]
    in_stock_product_ids: set[int]  # факт наличия — точный остаток покупателю не показываем
    sold_count_by_product_id: dict[int, Decimal]  # бейдж «Продано: N» — товары без продаж отсутствуют
    categories: list[StorefrontCategoryCount]
    warehouses: list[Warehouse]  # для выбора склада на самой странице витрины
    available_sizes: list[str]  # для фильтра «Размер» — только среди видимых на витрине товаров
    available_colors: list[str]  # для фильтра «Цвет»
    rating_by_product_id: dict[int, ProductRatingAggregate]  # только видимые отзывы
    total: int

    def to_json(self) -> dict:
        return {
            "shop_name": self.shop_name,
            "products": [p.to_dict() for p in self.products],
            "in_stock_product_ids": sorted(self.in_stock_product_ids),
            "sold_count_by_product_id": {
                str(pid): str(qty) for pid, qty in self.sold_count_by_product_id.items()
            },
            "categories": [
                {"category": c.category.to_dict(), "product_count": c.product_count}
                for c in self.categories
            ],
            "warehouses": [w.to_dict() for w in self.warehouses],
            "available_sizes": self.available_sizes,
            "available_colors": self.available_colors,
            "rating_by_product_id": {
                str(pid): {"average_rating": r.average_rating, "reviews_count": r.reviews_count}
                for pid, r in self.rating_by_product_id.items()
            },
            "total": self.total,
        }

    @classmethod
    def from_json(cls, d: dict) -> "StorefrontCatalogResult":
        return cls(
            shop_name=d["shop_name"],
            products=[Product.from_dict(p) for p in d["products"]],
            in_stock_product_ids=set(d["in_stock_product_ids"]),
            sold_count_by_product_id={
                int(pid): Decimal(qty)
                for pid, qty in d.get("sold_count_by_product_id", {}).items()
            },
            categories=[
                StorefrontCategoryCount(
                    category=Category.from_dict(c["category"]), product_count=c["product_count"]
                )
                for c in d["categories"]
            ],
            warehouses=[Warehouse.from_dict(w) for w in d["warehouses"]],
            available_sizes=d["available_sizes"],
            available_colors=d["available_colors"],
            rating_by_product_id={
                int(pid): ProductRatingAggregate(
                    average_rating=r["average_rating"], reviews_count=r["reviews_count"]
                )
                for pid, r in d.get("rating_by_product_id", {}).items()
            },
            total=d["total"],
        )


class GetStorefrontCatalogUseCase:
    """Публичный (без авторизации) каталог товаров магазина по Tenant.slug.

    Открывает свой UoW на резолвленный tenant_id — вызывающий (публичный
    роутер) не имеет аутентифицированного пользователя, поэтому обычный
    UowDep здесь неприменим.

    Результат кешируется на _CACHE_TTL_SECONDS (пять запросов к БД на один
    вызов, дергается анонимно). Без точной инвалидации по событиям —
    короткий TTL проще и безопаснее (промах = обычный пересчёт).
    """

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def _execute_uncached(
        self, cmd: GetStorefrontCatalogCommand
    ) -> StorefrontCatalogResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return None

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            all_warehouses = await uow.warehouses.list()
            visible_warehouse_ids = {w.id for w in all_warehouses if w.show_on_storefront}

            warehouse_id = cmd.warehouse_id
            if warehouse_id is not None and warehouse_id not in visible_warehouse_ids:
                # чужой/несуществующий/скрытый от витрины склад — тихо игнорируем фильтр,
                # не 404/400: не даём перебором узнавать, какие warehouse_id вообще существуют
                warehouse_id = None

            order_by = _SORT_ALIASES.get(cmd.sort)
            if order_by is None:
                raise DomainError(f"Неизвестная сортировка: «{cmd.sort}»")

            raw_params: dict = {
                "limit": cmd.limit,
                "offset": cmd.offset,
                "category_id": cmd.category_id,
                "show_on_storefront": True,
                "order_by": order_by,
            }
            if cmd.query.strip():
                raw_params["search_text__ilike"] = cmd.query.strip()
            if cmd.min_price is not None:
                raw_params["retail_price__gte"] = cmd.min_price
            if cmd.max_price is not None:
                raw_params["retail_price__lte"] = cmd.max_price
            if cmd.in_stock_only:
                raw_params["stock__gt"] = 0
            if cmd.with_discount:
                raw_params["discount_percent__is_null"] = False
            if cmd.min_rating is not None:
                raw_params["average_rating__gte"] = cmd.min_rating
            products, total = await uow.products.list_filtered(
                raw_params,
                warehouse_id=warehouse_id,
                warehouse_ids=None if warehouse_id is not None else list(visible_warehouse_ids),
                variant_size=cmd.variant_size,
                variant_color=cmd.variant_color,
            )
            all_categories = await uow.categories.list()
            counts = await uow.products.count_storefront_by_category()
            available_sizes, available_colors = await uow.products.list_storefront_variant_options()
            stock_items = await uow.stock.list_all()
            sold_counts = await uow.analytics.sold_count_by_products([p.id for p in products])
            rating_by_product_id = await uow.reviews.rating_by_products([p.id for p in products])
        in_stock_ids = {
            item.product_id
            for item in stock_items
            if item.quantity > 0
            and item.warehouse_id in visible_warehouse_ids
            and (warehouse_id is None or item.warehouse_id == warehouse_id)
        }
        warehouses = [w for w in all_warehouses if w.show_on_storefront]
        categories_with_counts = [
            StorefrontCategoryCount(category=c, product_count=counts[c.id])
            for c in all_categories
            if counts.get(c.id)
        ]
        return StorefrontCatalogResult(
            shop_name=tenant.name,
            products=products,
            in_stock_product_ids=in_stock_ids,
            sold_count_by_product_id=sold_counts,
            categories=categories_with_counts,
            warehouses=warehouses,
            available_sizes=available_sizes,
            available_colors=available_colors,
            rating_by_product_id=rating_by_product_id,
            total=total,
        )

    execute = cached_use_case(
        "storefront_catalog",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=StorefrontCatalogResult.from_json,
        shop_slug=lambda cmd: cmd.slug,
    )(_execute_uncached)
