from dataclasses import dataclass

from app.domain.catalog.entities import Product
from app.domain.common.uow import IUnitOfWork


@dataclass(frozen=True)
class ProductsExportData:
    products: list[Product]
    category_names: dict[int, str]
    shop_name: str


class GetProductsExportDataUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self) -> ProductsExportData:
        async with self._uow as uow:
            # только товары: импорт про вид позиции не знает, и выгруженная
            # услуга при обратном импорте вернулась бы товаром со складом
            products = [p for p in await uow.products.search_all() if not p.is_service]
            categories = await uow.categories.list()
            tenant = await uow.tenants.get(uow.tenant_id)
            category_names = {c.id: c.name for c in categories}
            return ProductsExportData(
                products=products, category_names=category_names, shop_name=tenant.name
            )
