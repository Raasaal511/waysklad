from app.domain.catalog.entities import Category
from app.domain.common.uow import IUnitOfWork


class ListCategoriesUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self) -> list[Category]:
        async with self._uow as uow:
            return await uow.categories.list()
