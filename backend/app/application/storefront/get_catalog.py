from dataclasses import dataclass

from app.domain.catalog.entities import Category, Product
from app.domain.common.exceptions import DomainError, NotFoundError
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
            warehouse_id = cmd.warehouse_id
            if warehouse_id is not None:
                try:
                    await uow.warehouses.get(warehouse_id)
                except NotFoundError:
                    # чужой/несуществующий склад — тихо игнорируем фильтр, не 404/400:
                    # не даём перебором узнавать, какие warehouse_id вообще существуют
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
            products, total = await uow.products.list_filtered(raw_params)
            all_categories = await uow.categories.list()
            counts = await uow.products.count_storefront_by_category()
            stock_items = await uow.stock.list_all()
        in_stock_ids = {
            item.product_id
            for item in stock_items
            if item.quantity > 0 and (warehouse_id is None or item.warehouse_id == warehouse_id)
        }
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
            total=total,
        )
