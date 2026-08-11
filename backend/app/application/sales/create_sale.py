from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError, InsufficientStockError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt, total_balance
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.sales.entities import Sale, SaleLine
from app.domain.sales.payment import PaymentMethod


@dataclass(frozen=True)
class SaleItemInput:
    product_id: int
    quantity: Decimal
    price: Decimal  # цена продажи (может отличаться от розничной)
    variant_id: int | None = None


@dataclass(frozen=True)
class CreateSaleCommand:
    warehouse_id: int
    payment_method: PaymentMethod
    items: list[SaleItemInput]
    discount: Decimal = Decimal("0")
    client_id: int | None = None
    cash_received: Decimal | None = None  # для расчёта сдачи
    client_op_id: str | None = None  # id операции с устройства — идемпотентность офлайн-очереди
    debt_due_date: date | None = None  # «долг до» — обязателен при payment_method=CREDIT


@dataclass(frozen=True)
class CreateSaleResult:
    sale: Sale
    change: Money | None  # сдача (если передали cash_received)


class CreateSaleUseCase:
    """Экран быстрой продажи: скан → количество → скидка → способ оплаты → готово."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateSaleCommand) -> CreateSaleResult:
        require(actor, Permission.SALES_CREATE)

        async with self._uow as uow:
            if cmd.client_op_id is not None:
                existing = await uow.sales.get_by_client_op_id(cmd.client_op_id)
                if existing is not None:
                    # уже применено раньше — повторная отправка из офлайн-очереди
                    return CreateSaleResult(sale=existing, change=None)

            lines = []
            names = {}
            for item in cmd.items:
                product = await uow.products.get(item.product_id)
                names[product.id] = product.name
                lines.append(
                    SaleLine(
                        product_id=item.product_id,
                        variant_id=item.variant_id,
                        quantity=Quantity(item.quantity, product.unit),
                        price=Money.of(item.price),
                        purchase_price=product.purchase_price,
                    )
                )

            sale = Sale(
                id=None,
                warehouse_id=cmd.warehouse_id,
                seller_id=actor.id,
                payment_method=cmd.payment_method,
                lines=lines,
                discount=Money.of(cmd.discount),
                client_id=cmd.client_id,
                client_op_id=cmd.client_op_id,
                cash_received=Money.of(cmd.cash_received) if cmd.cash_received is not None else None,
            )
            sale.validate()

            if sale.payment_method is PaymentMethod.CREDIT and cmd.debt_due_date is None:
                raise DomainError("Для продажи в долг нужно указать срок «Долг до»")

            for line in sale.lines:
                new_quantity = await uow.stock.change(
                    line.product_id, sale.warehouse_id, -line.quantity.value, line.variant_id
                )
                if new_quantity < 0:
                    raise InsufficientStockError(
                        f"Недостаточно остатка: {names[line.product_id]}"
                    )

            if sale.payment_method is PaymentMethod.CREDIT:
                await self._check_debt_limit(uow, sale)

            await uow.sales.add(sale)

            if sale.payment_method is PaymentMethod.CREDIT:
                debt = Debt(
                    id=None,
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
            await uow.audit.add(
                AuditEntry.record(
                    actor, "sale.create", sale.id,
                    total=str(sale.total.amount),
                    payment_method=sale.payment_method.value,
                    client_id=sale.client_id,
                )
            )
            await uow.commit()
            return CreateSaleResult(sale=sale, change=change)

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
