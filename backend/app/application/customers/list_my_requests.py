from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.domain.common.money import Money
from app.domain.storefront.entities import StorefrontRequest, StorefrontRequestStatus
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

DEFAULT_LIMIT = 20


@dataclass(frozen=True)
class MyRequestLine:
    """Позиция заявки с тем, что нужно карточке заказа: название, фото и цена
    берутся из товара магазина, количество — из самой заявки."""

    product_id: int
    name: str
    photo: str
    quantity: Decimal
    price: Decimal
    total: Decimal


@dataclass(frozen=True)
class MyStorefrontRequestItem:
    request: StorefrontRequest
    shop_name: str
    shop_slug: str = ""
    shop_logo: str = ""
    lines: list[MyRequestLine] = field(default_factory=list)
    total: Decimal = Decimal("0")
    # заполнено только у принятых заявок (у них есть Order)
    due_date: date | None = None
    order_total: Decimal | None = None
    prepayment: Decimal | None = None
    to_pay: Decimal | None = None
    order_status: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class ListMyRequestsResult:
    items: list[MyStorefrontRequestItem]
    total: int


class ListMyStorefrontRequestsUseCase:
    """Все заявки авторизованного покупателя во всех магазинах платформы —
    аналог owner-side GetStorefrontRequestStatusUseCase, но по customer_id,
    не по access_token одной конкретной заявки.

    Против N+1: заявки сгруппированы по магазинам, и на каждый магазин
    приходится по одному обращению за товарами и заказами, а не по одному на
    заявку. Товары лежат в tenant-scoped таблицах, поэтому меньше чем одним
    UoW на магазин обойтись нельзя — но число обращений зависит от количества
    магазинов покупателя (обычно 1-3), а не от числа заказов.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(
        self,
        customer_id: int,
        status: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> ListMyRequestsResult:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            requests = await uow.storefront_requests.list_by_customer(customer_id)
            tenants = await uow.tenants.list_all()

        if status:
            requests = [r for r in requests if r.status.value == status]

        total = len(requests)
        page = requests[offset : offset + limit]
        if not page:
            return ListMyRequestsResult(items=[], total=total)

        tenant_by_id = {t.id: t for t in tenants}

        by_tenant: dict[int, list[StorefrontRequest]] = defaultdict(list)
        for request in page:
            if request.tenant_id is not None:
                by_tenant[request.tenant_id].append(request)

        enriched: dict[int, MyStorefrontRequestItem] = {}
        for tenant_id, tenant_requests in by_tenant.items():
            tenant = tenant_by_id.get(tenant_id)
            product_ids = {
                line.product_id for r in tenant_requests for line in r.lines
            }
            order_ids = {r.order_id for r in tenant_requests if r.order_id is not None}

            async with SqlAlchemyUnitOfWork(
                tenant_id, session_factory=self._session_factory
            ) as tenant_uow:
                products = await tenant_uow.products.list_by_ids(sorted(product_ids))
                orders = {}
                for order_id in sorted(order_ids):
                    try:
                        orders[order_id] = await tenant_uow.orders.get(order_id)
                    except Exception:
                        # заказ мог быть удалён — заявка остаётся видимой,
                        # просто без сумм и даты готовности
                        continue

            product_by_id = {p.id: p for p in products}

            for request in tenant_requests:
                lines: list[MyRequestLine] = []
                request_total = Decimal("0")
                for line in request.lines:
                    product = product_by_id.get(line.product_id)
                    price = (
                        product.retail_price.amount if product else Decimal("0")
                    )
                    # через Money — иначе Decimal умножает знаки после запятой
                    # (120.00 * 2.000 = 240.00000) и фронт получает такую строку
                    line_total = Money(price * line.quantity).amount
                    request_total += line_total
                    lines.append(
                        MyRequestLine(
                            product_id=line.product_id,
                            name=product.name if product else "Товар удалён",
                            photo=product.photo if product else "",
                            quantity=line.quantity,
                            price=price,
                            total=line_total,
                        )
                    )

                order = orders.get(request.order_id) if request.order_id else None
                enriched[id(request)] = MyStorefrontRequestItem(
                    request=request,
                    shop_name=tenant.name if tenant else "",
                    shop_slug=tenant.slug if tenant else "",
                    shop_logo=tenant.logo if tenant else "",
                    lines=lines,
                    total=Money(request_total).amount,
                    created_at=request.created_at,
                    due_date=order.due_date if order else None,
                    order_total=_amount(order.total) if order else None,
                    prepayment=_amount(order.prepayment) if order else None,
                    to_pay=_amount(order.to_pay) if order else None,
                    order_status=order.status.value if order else None,
                )

        # порядок исходного списка (новые сверху) — dict по id() сохраняет его
        items = [enriched[id(r)] for r in page if id(r) in enriched]
        return ListMyRequestsResult(items=items, total=total)


def _amount(money: Money) -> Decimal:
    return money.amount


__all__ = [
    "DEFAULT_LIMIT",
    "ListMyRequestsResult",
    "ListMyStorefrontRequestsUseCase",
    "MyRequestLine",
    "MyStorefrontRequestItem",
    "StorefrontRequestStatus",
]
