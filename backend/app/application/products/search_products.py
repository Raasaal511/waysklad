from dataclasses import dataclass

from app.domain.catalog.entities import Product
from app.domain.common.uow import IUnitOfWork


@dataclass(frozen=True)
class SearchProductsCommand:
    raw_params: dict
    warehouse_id: int | None = None


@dataclass(frozen=True)
class SearchProductsResult:
    products: list[Product]
    total: int


class SearchProductsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, cmd: SearchProductsCommand) -> SearchProductsResult:
        async with self._uow as uow:
            products, total = await uow.products.list_filtered(
                cmd.raw_params, warehouse_id=cmd.warehouse_id
            )
            return SearchProductsResult(products=products, total=total)
