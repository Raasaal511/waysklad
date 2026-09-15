from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product
from app.domain.common.uow import IUnitOfWork


class GetProductByBarcodeUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, barcode: Barcode) -> Product | None:
        async with self._uow as uow:
            return await uow.products.get_by_barcode(barcode)
