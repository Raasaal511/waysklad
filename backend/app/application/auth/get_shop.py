from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Tenant


class GetShopUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self) -> Tenant:
        async with self._uow as uow:
            return await uow.tenants.get(uow.tenant_id)
