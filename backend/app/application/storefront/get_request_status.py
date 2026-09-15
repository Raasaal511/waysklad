from dataclasses import dataclass

from app.domain.orders.entities import Order
from app.domain.storefront.entities import StorefrontRequest
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class GetStorefrontRequestStatusCommand:
    access_token: str


@dataclass(frozen=True)
class StorefrontRequestStatusResult:
    request: StorefrontRequest
    order: Order | None  # заполнен только если заявка принята


class GetStorefrontRequestStatusUseCase:
    """Покупатель без аккаунта проверяет статус своей заявки по access_token —
    после принятия видит дату готовности и сумму к оплате."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: GetStorefrontRequestStatusCommand) -> StorefrontRequestStatusResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            request = await public_uow.storefront_requests.get_by_token(cmd.access_token)
        if request is None:
            return None

        order = None
        if request.order_id is not None:
            async with SqlAlchemyUnitOfWork(
                request.tenant_id, session_factory=self._session_factory
            ) as uow:
                order = await uow.orders.get(request.order_id)
        return StorefrontRequestStatusResult(request=request, order=order)
