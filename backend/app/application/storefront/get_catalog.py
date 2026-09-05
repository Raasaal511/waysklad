from dataclasses import dataclass
from decimal import Decimal

from app.domain.catalog.entities import Category, Product
from app.domain.common.exceptions import DomainError
from app.domain.identity.entities import Warehouse
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

# покупателю доступна только эта часть сортировок ProductFilterFactory —
# ни margin (закупочная маржа), ни stock (точный остаток) публично не отдаются
_SORT_ALIASES = {
    "name": "name",
    "price_asc": "retail_price",
    "price_desc": "-retail_price",
    "created_desc": "-created_at",
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
    variant_size: str | None = None
    variant_color: str | None = None


@dataclass(frozen=True)
class StorefrontCategoryCount:
    category: Category
    product_count: int


@dataclass(frozen=True)
class StorefrontCatalogResult:
    shop_name: str
    products: list[Product]
    in_stock_product_ids: set[int]  # факт наличия — точный остаток покупателю не показываем
    categories: list[StorefrontCategoryCount]
    warehouses: list[Warehouse]  # для выбора склада на самой странице витрины
    available_sizes: list[str]  # для фильтра «Размер» — только среди видимых на витрине товаров
    available_colors: list[str]  # для фильтра «Цвет»
    total: int


class GetStorefrontCatalogUseCase:
    """Публичный (без авторизации) каталог товаров магазина по Tenant.slug.

    Открывает свой UoW на резолвленный tenant_id — вызывающий (публичный
    роутер) не имеет аутентифицированного пользователя, поэтому обычный
    UowDep здесь неприменим.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: GetStorefrontCatalogCommand) -> StorefrontCatalogResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled:
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
            categories=categories_with_counts,
            warehouses=warehouses,
            available_sizes=available_sizes,
            available_colors=available_colors,
            total=total,
        )
