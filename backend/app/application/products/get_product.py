from app.domain.catalog.entities import Product
from app.domain.common.uow import IUnitOfWork


class GetProductUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, product_id: int) -> Product:
        async with self._uow as uow:
            return await uow.products.get(product_id)
