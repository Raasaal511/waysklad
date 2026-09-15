from app.domain.common.uow import IUnitOfWork
from app.domain.storefront.entities import StorefrontRequest


class GetStorefrontRequestUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, request_id: int) -> StorefrontRequest:
        async with self._uow as uow:
            return await uow.storefront_requests.get(request_id)
