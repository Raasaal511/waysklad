from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.storefront.reservation import release_request_reservation
from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError, InsufficientStockError
from app.domain.common.money import Money
from app.domain.common.phone import Phone
from app.domain.common.quantity import Quantity
from app.domain.common.uow import IUnitOfWork
from app.domain.counterparties.entities import Client
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse
from app.domain.orders.entities import Order, OrderLine, OrderSource
from app.domain.storefront.entities import StorefrontRequestStatus
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class AcceptStorefrontRequestCommand:
    request_id: int
    warehouse_id: int
    due_date: date
    prepayment: Decimal = Decimal("0")


class AcceptStorefrontRequestUseCase:
    """Владелец/менеджер принимает сырую заявку с витрины: указывает склад и дату
    готовности — только тогда она становится настоящим Order с резервом остатка."""

    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: AcceptStorefrontRequestCommand) -> Order:
        require(actor, Permission.ORDERS_MANAGE)
        require_warehouse(actor, cmd.warehouse_id)

        async with self._uow as uow:
            request = await uow.storefront_requests.get(cmd.request_id)
            if request.status != StorefrontRequestStatus.NEW:
                raise DomainError("Заявка уже обработана")

            if not request.reservation_released:
                # мягкий резерв под заявку (CreateStorefrontRequestUseCase) мог
                # осесть на любом видимом складе — снимаем его весь, чтобы ниже
                # переставить резерв уже конкретно на выбранный владельцем склад
                await release_request_reservation(uow, request)

            client = None
            phone = Phone(request.customer_phone) if request.customer_phone else None
            if phone is not None:
                client = await uow.clients.get_by_phone(str(phone))
            if client is None:
                client = await uow.clients.add(
                    Client(id=None, name=request.customer_name, phone=phone)
                )
                await uow.audit.add(
                    AuditEntry.record(actor, "client.create", client.id, name=client.name)
                )

            lines = []
            for item in request.lines:
                product = await uow.products.get(item.product_id)
                lines.append(
                    OrderLine(
                        product_id=item.product_id,
                        variant_id=item.variant_id,
                        quantity=Quantity(item.quantity, product.unit),
                        price=product.retail_price,
                    )
                )
                new_reserved = await uow.stock.reserve(
                    item.product_id, cmd.warehouse_id, item.quantity, item.variant_id
                )
                on_hand = await uow.stock.get(item.product_id, cmd.warehouse_id, item.variant_id)
                if new_reserved > on_hand:
                    raise InsufficientStockError(f"Недостаточно остатка: {product.name}")

            new_order = Order(
                id=None,
                client_id=client.id,
                warehouse_id=cmd.warehouse_id,
                lines=lines,
                due_date=cmd.due_date,
                prepayment=Money.of(cmd.prepayment),
                source=OrderSource.STOREFRONT,
                note=request.note,
            )
            new_order.validate()
            order = await uow.orders.add(new_order)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "order.create", order.id,
                    client_id=client.id, total=str(order.total.amount), source="storefront",
                )
            )

            request.accept(order.id)
            await uow.storefront_requests.save(request)
            await uow.audit.add(
                AuditEntry.record(actor, "storefront_request.accept", request.id, order_id=order.id)
            )

            await uow.commit()
            # accept меняет orders_count публичного профиля магазина (промпт B2 п.2) —
            # без явной инвалидации счётчик отставал бы до истечения TTL кеша профиля
            await invalidate_shop_cache(self._cache, uow)
            return order
