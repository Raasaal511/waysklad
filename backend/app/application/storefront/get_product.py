import dataclasses
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.domain.catalog.entities import Category, Product, stock_level
from app.domain.common.cache import ICache
from app.domain.common.exceptions import NotFoundError
from app.domain.reviews.repository import ProductRatingAggregate
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 20
_EMPTY_RATING = ProductRatingAggregate(average_rating=0.0, reviews_count=0)
_VIEWS_WINDOW_DAYS = 90


@dataclass(frozen=True)
class GetStorefrontProductCommand:
    slug: str
    product_id: int


@dataclass(frozen=True)
class VariantStock:
    """Наличие одного варианта — часть StorefrontProductResult, не самого
    domain ProductVariant: видимость остатка зависит от настройки Tenant,
    это забота витрины, а не складской модели."""

    variant_id: int
    in_stock: bool
    stock_level: str
    quantity: Decimal  # видимый остаток на видимых складах — сырое число для stock_qty


@dataclass(frozen=True)
class CategoryWithParent:
    category: Category
    parent: Category | None


@dataclass(frozen=True)
class StorefrontProductResult:
    shop_name: str
    product: Product
    in_stock: bool
    stock_level: str
    stock_qty: Decimal | None  # None — товар без остатка на видимых складах
    show_stock_qty: bool  # Tenant.storefront_show_stock_qty — решает, отдавать ли stock_qty
    variant_stock: dict[int, VariantStock]
    category: CategoryWithParent | None
    sold_count: Decimal
    rating: ProductRatingAggregate
    views_90d: int

    def to_json(self) -> dict:
        return {
            "shop_name": self.shop_name,
            "product": self.product.to_dict(),
            "in_stock": self.in_stock,
            "stock_level": self.stock_level,
            "stock_qty": str(self.stock_qty) if self.stock_qty is not None else None,
            "show_stock_qty": self.show_stock_qty,
            "variant_stock": {
                str(vid): {
                    "in_stock": vs.in_stock,
                    "stock_level": vs.stock_level,
                    "quantity": str(vs.quantity),
                }
                for vid, vs in self.variant_stock.items()
            },
            "category": (
                {
                    "category": self.category.category.to_dict(),
                    "parent": self.category.parent.to_dict() if self.category.parent else None,
                }
                if self.category is not None
                else None
            ),
            "sold_count": str(self.sold_count),
            "rating": {
                "average_rating": self.rating.average_rating,
                "reviews_count": self.rating.reviews_count,
            },
            # views_90d намеренно не кешируется по значению — просмотры не должны
            # инвалидировать кэш карточки (промпт B1 п.5), поэтому пересчитывается
            # заново при каждом обращении, даже если остальной ответ взят из кеша
        }

    @classmethod
    def from_json(cls, d: dict) -> "StorefrontProductResult":
        rating_d = d.get("rating")
        category_d = d.get("category")
        return cls(
            shop_name=d["shop_name"],
            product=Product.from_dict(d["product"]),
            in_stock=d["in_stock"],
            stock_level=d.get("stock_level", "in" if d["in_stock"] else "out"),
            stock_qty=Decimal(d["stock_qty"]) if d.get("stock_qty") is not None else None,
            show_stock_qty=d.get("show_stock_qty", False),
            variant_stock={
                int(vid): VariantStock(
                    variant_id=int(vid),
                    in_stock=vs["in_stock"],
                    stock_level=vs["stock_level"],
                    quantity=Decimal(vs["quantity"]),
                )
                for vid, vs in d.get("variant_stock", {}).items()
            },
            category=(
                CategoryWithParent(
                    category=Category.from_dict(category_d["category"]),
                    parent=Category.from_dict(category_d["parent"])
                    if category_d.get("parent")
                    else None,
                )
                if category_d is not None
                else None
            ),
            sold_count=Decimal(d.get("sold_count", "0")),
            rating=ProductRatingAggregate(**rating_d) if rating_d else _EMPTY_RATING,
            views_90d=0,  # пересчитывается заново после чтения из кеша, см. execute()
        )


class GetStorefrontProductUseCase:
    """Карточка одного товара на публичной витрине — для отдельной ссылки,
    например «скинуть этот товар клиенту в WhatsApp».

    Результат кешируется на _CACHE_TTL_SECONDS — та же логика, что у
    GetStorefrontCatalogUseCase (короткий TTL вместо точной инвалидации).
    views_90d — исключение: он не должен ждать инвалидации кэша каждым
    просмотром, поэтому пересчитывается отдельным запросом при каждом
    вызове execute(), уже поверх результата _cached_execute()."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def _execute_uncached(
        self, cmd: GetStorefrontProductCommand
    ) -> StorefrontProductResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return None

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            try:
                product = await uow.products.get(cmd.product_id)
            except NotFoundError:
                return None
            if not product.show_on_storefront:
                return None
            all_warehouses = await uow.warehouses.list()
            visible_warehouse_ids = {w.id for w in all_warehouses if w.show_on_storefront}
            stock_items = await uow.stock.list_all()
            sold_counts = await uow.analytics.sold_count_by_products([product.id])
            ratings = await uow.reviews.rating_by_products([product.id])
            all_categories = await uow.categories.list()

        # остаток товара целиком — сумма по вариантам и позициям без варианта,
        # только на складах, видимых витрине (см. промпт B1 п.2). Затравка
        # суммы — Decimal("0.000"), не Decimal("0"): та же точность (14,3),
        # что у stock_items.quantity, иначе пустая сумма отдаёт "0" без нулей
        # после точки, а непустая — "7.000" (несогласованный формат stock_qty)
        _ZERO = Decimal("0.000")
        product_qty = sum(
            (
                item.quantity
                for item in stock_items
                if item.product_id == product.id and item.warehouse_id in visible_warehouse_ids
            ),
            _ZERO,
        )
        variant_qty: dict[int, Decimal] = {}
        for item in stock_items:
            if (
                item.product_id == product.id
                and item.variant_id is not None
                and item.warehouse_id in visible_warehouse_ids
            ):
                variant_qty[item.variant_id] = variant_qty.get(item.variant_id, _ZERO) + item.quantity

        variant_stock = {
            v.id: VariantStock(
                variant_id=v.id,
                in_stock=variant_qty.get(v.id, _ZERO) > 0,
                stock_level=stock_level(variant_qty.get(v.id, _ZERO), product.min_stock),
                quantity=variant_qty.get(v.id, _ZERO),
            )
            for v in product.variants
            if v.id is not None
        }

        category = None
        if product.category_id is not None:
            by_id = {c.id: c for c in all_categories}
            found = by_id.get(product.category_id)
            if found is not None:
                parent = by_id.get(found.parent_id) if found.parent_id is not None else None
                category = CategoryWithParent(category=found, parent=parent)

        sold_count = sold_counts.get(product.id, Decimal("0"))
        rating = ratings.get(product.id, _EMPTY_RATING)
        return StorefrontProductResult(
            shop_name=tenant.name,
            product=product,
            in_stock=product_qty > 0,
            stock_level=stock_level(product_qty, product.min_stock),
            stock_qty=product_qty if tenant.storefront_show_stock_qty else None,
            show_stock_qty=tenant.storefront_show_stock_qty,
            variant_stock=variant_stock,
            category=category,
            sold_count=sold_count,
            rating=rating,
            views_90d=0,  # пересчитывается в execute() поверх cache-aside, см. ниже
        )

    async def _views_90d(self, uow: SqlAlchemyUnitOfWork, product_id: int) -> int:
        since = date.today() - timedelta(days=_VIEWS_WINDOW_DAYS - 1)
        return await uow.product_views.views_since(product_id, since)

    async def execute(self, cmd: GetStorefrontProductCommand) -> StorefrontProductResult | None:
        result = await self._cached_execute(cmd)
        if result is None:
            return result
        # views_90d специально не участвует в to_json/from_json по значению —
        # пересчитывается при каждом вызове поверх кешированного остального
        # ответа (промпт B1 п.5: просмотры не должны ждать TTL кэша карточки).
        # product.id и tenant уже известны из закешированного result — второй
        # tenant-lookup не нужен, tenant_id ищем один раз через сам продукт.
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None:
            return None
        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            views_90d = await self._views_90d(uow, cmd.product_id)
        return dataclasses.replace(result, views_90d=views_90d)

    _cached_execute = cached_use_case(
        "storefront_product",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=StorefrontProductResult.from_json,
        shop_slug=lambda cmd: cmd.slug,
    )(_execute_uncached)
