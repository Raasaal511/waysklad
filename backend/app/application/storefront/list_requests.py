from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.storefront.entities import StorefrontRequest


class ListStorefrontRequestsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[StorefrontRequest]:
        require(actor, Permission.ORDERS_VIEW)
        async with self._uow as uow:
            return await uow.storefront_requests.list_new()
