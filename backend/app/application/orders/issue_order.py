from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt, total_balance
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse
from app.domain.orders.entities import Order, OrderStatus
from app.domain.sales.entities import Sale, SaleLine
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class IssueOrderCommand:
    order_id: int
    payment_method: PaymentMethod
    cash_received: Decimal | None = None  # для расчёта сдачи
    change_kept: Decimal = Decimal("0")   # клиент не забрал (часть) сдачи
    debt_due_date: date | None = None     # обязателен при payment_method=CREDIT


@dataclass(frozen=True)
class IssueOrderResult:
    order: Order
    sale: Sale
    change: Money | None


class IssueOrderUseCase:
    """Выдача готового заказа = продажа: резерв снимается, остаток физически
    списывается, доплата (сумма за вычетом предоплаты) закрывается тем же
    способом оплаты, что и обычная продажа (наличные/перевод/долг)."""

    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: IssueOrderCommand) -> IssueOrderResult:
        require(actor, Permission.ORDERS_MANAGE)

        async with self._uow as uow:
            order = await uow.orders.get(cmd.order_id)
            require_warehouse(actor, order.warehouse_id)
            if order.status != OrderStatus.READY:
                raise DomainError("Выдать можно только заказ в статусе «Готов»")

            lines = []
            for line in order.lines:
                product = await uow.products.get(line.product_id)
                lines.append(
                    SaleLine(
                        product_id=line.product_id,
                        variant_id=line.variant_id,
                        quantity=line.quantity,
                        price=line.price,
                        purchase_price=product.purchase_price,
                    )
                )

            # Предоплата уже получена раньше — Sale.prepayment уменьшает только
            # то, что нужно доплатить сейчас (sale.total), но не выручку:
            # аналитика считает revenue по полным ценам строк за вычетом
            # только discount, prepayment в неё не входит намеренно.
            sale = Sale(
                id=None,
                warehouse_id=order.warehouse_id,
                seller_id=actor.id,
                payment_method=cmd.payment_method,
                lines=lines,
                prepayment=order.prepayment,
                client_id=order.client_id,
                cash_received=(
                    Money.of(cmd.cash_received) if cmd.cash_received is not None else None
                ),
                change_kept=Money.of(cmd.change_kept),
                note=f"Из заказа №{order.number}",
                order_id=order.id,
            )
            sale.validate()

            if sale.payment_method is PaymentMethod.CREDIT and cmd.debt_due_date is None:
                raise DomainError("Для продажи в долг нужно указать срок «Долг до»")

            for line in order.lines:
                await uow.stock.reserve(
                    line.product_id, order.warehouse_id, -line.quantity.value, line.variant_id
                )
                new_quantity = await uow.stock.change(
                    line.product_id, order.warehouse_id, -line.quantity.value, line.variant_id
                )
                if new_quantity < 0:
                    # резерв на этапе создания заказа гарантировал остаток на тот
                    # момент — отрицательный итог здесь означает, что остаток
                    # уменьшили мимо резерва (например, инвентаризацией) уже
                    # после того, как заказ был зарезервирован
                    product = await uow.products.get(line.product_id)
                    raise DomainError(
                        f"Недостаточно остатка «{product.name}» для выдачи — "
                        "проверьте остаток на складе"
                    )

            if sale.payment_method is PaymentMethod.CREDIT:
                await self._check_debt_limit(uow, sale)

            await uow.sales.add(sale)

            if sale.payment_method is PaymentMethod.CREDIT:
                debt = Debt(
                    id=None,
                    warehouse_id=order.warehouse_id,
                    client_id=sale.client_id,
                    amount=sale.total,
                    issued_at=date.today(),
                    due_date=cmd.debt_due_date,
                    sale_id=sale.id,
                )
                debt.validate()
                await uow.debts.add(debt)

            change = (
                sale.change_for(Money.of(cmd.cash_received))
                if cmd.cash_received is not None
                else None
            )

            order.sale_id = sale.id
            order.change_status(OrderStatus.ISSUED)
            await uow.orders.save(order)

            await uow.audit.add(
                AuditEntry.record(
                    actor, "order.issue", order.id,
                    sale_id=sale.id, total=str(sale.total.amount),
                )
            )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "sale.create", sale.id,
                    total=str(sale.total.amount),
                    payment_method=sale.payment_method.value,
                    client_id=sale.client_id,
                )
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
            return IssueOrderResult(order=order, sale=sale, change=change)

    @staticmethod
    async def _check_debt_limit(uow: IUnitOfWork, sale: Sale) -> None:
        client = await uow.clients.get(sale.client_id)
        if client.debt_limit is None:
            return
        balance = sale.total + total_balance(await uow.debts.list_by_client(client.id))
        if balance > client.debt_limit:
            raise DomainError(
                f"Превышен лимит долга клиента «{client.name}»: "
                f"{balance} при лимите {client.debt_limit}"
            )
