from dataclasses import dataclass

from app.domain.catalog.entities import Category, Product
from app.domain.common.exceptions import NotFoundError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class GetStorefrontCatalogCommand:
    slug: str
    query: str = ""
    limit: int = 50
    offset: int = 0
    category_id: int | None = None
    warehouse_id: int | None = None  # витрина одного склада — наличие считается только по нему


@dataclass(frozen=True)
class StorefrontCatalogResult:
    shop_name: str
    products: list[Product]
    in_stock_product_ids: set[int]  # факт наличия — точный остаток покупателю не показываем
    categories: list[Category]
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

            raw_params: dict = {
                "limit": cmd.limit,
                "offset": cmd.offset,
                "category_id": cmd.category_id,
                "show_on_storefront": True,
            }
            if cmd.query.strip():
                raw_params["search_text__ilike"] = cmd.query.strip()
            products, total = await uow.products.list_filtered(raw_params)
            categories = await uow.categories.list()
            stock_items = await uow.stock.list_all()
        in_stock_ids = {
            item.product_id
            for item in stock_items
            if item.quantity > 0 and (warehouse_id is None or item.warehouse_id == warehouse_id)
        }
        return StorefrontCatalogResult(
            shop_name=tenant.name,
            products=products,
            in_stock_product_ids=in_stock_ids,
            categories=categories,
            total=total,
        )
