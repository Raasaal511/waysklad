from app.domain.catalog.entities import Unit
from app.domain.common.uow import IUnitOfWork


class ListUnitsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self) -> list[Unit]:
        async with self._uow as uow:
            return await uow.units.list()
