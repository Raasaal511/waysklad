from dataclasses import dataclass

from app.domain.customers.entities import Customer
from app.domain.storefront.entities import StorefrontRequestStatus
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class CustomerProfileStats:
    requests_total: int
    requests_accepted: int
    requests_rejected: int
    # «в работе» — заявка отправлена, магазин ещё не ответил
    requests_active: int = 0
    # в скольких разных магазинах покупатель заказывал
    shops_count: int = 0


@dataclass(frozen=True)
class CustomerProfileResult:
    customer: Customer
    stats: CustomerProfileStats


class GetCustomerProfileUseCase:
    """Личный кабинет покупателя — данные аккаунта + сводная статистика по
    заявкам со всех магазинов платформы (тот же источник, что
    ListMyStorefrontRequestsUseCase, но агрегированный, не постатейно)."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, customer_id: int) -> CustomerProfileResult:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            customer = await uow.customers.get(customer_id)
            requests = await uow.storefront_requests.list_by_customer(customer_id)

        stats = CustomerProfileStats(
            requests_total=len(requests),
            requests_accepted=sum(
                1 for r in requests if r.status == StorefrontRequestStatus.ACCEPTED
            ),
            requests_rejected=sum(
                1 for r in requests if r.status == StorefrontRequestStatus.REJECTED
            ),
            requests_active=sum(
                1 for r in requests if r.status == StorefrontRequestStatus.NEW
            ),
            shops_count=len({r.tenant_id for r in requests if r.tenant_id is not None}),
        )
        return CustomerProfileResult(customer=customer, stats=stats)
