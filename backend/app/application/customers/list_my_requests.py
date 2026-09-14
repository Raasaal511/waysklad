from dataclasses import dataclass

from app.domain.storefront.entities import StorefrontRequest
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class MyStorefrontRequestItem:
    request: StorefrontRequest
    shop_name: str


class ListMyStorefrontRequestsUseCase:
    """Все заявки авторизованного покупателя во всех магазинах платформы —
    аналог owner-side GetStorefrontRequestStatusUseCase, но по customer_id,
    не по access_token одной конкретной заявки."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, customer_id: int) -> list[MyStorefrontRequestItem]:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            requests = await uow.storefront_requests.list_by_customer(customer_id)
            tenants = await uow.tenants.list_all()

        shop_name_by_tenant = {t.id: t.name for t in tenants}
        return [
            MyStorefrontRequestItem(
                request=r, shop_name=shop_name_by_tenant.get(r.tenant_id, "")
            )
            for r in requests
        ]
