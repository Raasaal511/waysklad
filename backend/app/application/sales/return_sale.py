from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse
from app.domain.sales.entities import Sale, SaleReturn, SaleReturnLine
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class ReturnItemInput:
    sale_line_id: int
    quantity: Decimal


@dataclass(frozen=True)
class ReturnSaleCommand:
    sale_id: int
    items: list[ReturnItemInput]
    note: str = ""
    client_op_id: str | None = None  # id операции с устройства — идемпотентность офлайн-очереди


@dataclass(frozen=True)
class ReturnSaleResult:
    sale_return: SaleReturn
    refund: Money  # сумма возврата по товарам
    cash_to_client: Money  # сколько вернуть наличными (сверх погашения долга)


class ReturnSaleUseCase:
    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: ReturnSaleCommand) -> ReturnSaleResult:
        require(actor, Permission.SALES_RETURN)

        async with self._uow as uow:
            if cmd.client_op_id is not None:
                existing = await uow.sale_returns.get_by_client_op_id(cmd.client_op_id)
                if existing is not None:
                    return ReturnSaleResult(
                        sale_return=existing, refund=Money.zero(), cash_to_client=Money.zero()
                    )

            sale = await uow.sales.get(cmd.sale_id)
            require_warehouse(actor, sale.warehouse_id)
            lines_by_id = {line.id: line for line in sale.lines}
            already_returned = self._already_returned(await uow.sale_returns.list_by_sale(sale.id))

            return_lines = []
            refund = Money.zero()
            for item in cmd.items:
                sale_line = lines_by_id.get(item.sale_line_id)
                if sale_line is None:
                    raise DomainError(
                        f"Строка {item.sale_line_id} не относится к продаже {sale.id}"
                    )
                returned = already_returned.get(sale_line.id, Decimal("0"))
                remaining = sale_line.quantity.value - returned
                if item.quantity > remaining:
                    raise DomainError(
                        f"Нельзя вернуть больше проданного (доступно к возврату: {remaining})"
                    )
                return_lines.append(
                    SaleReturnLine(
                        sale_line_id=sale_line.id,
                        quantity=Quantity(item.quantity, sale_line.quantity.unit),
                    )
                )
                refund = refund + sale_line.price * item.quantity

            sale_return = SaleReturn(
                id=None, sale_id=sale.id, author_id=actor.id, lines=return_lines, note=cmd.note,
                client_op_id=cmd.client_op_id,
            )
            sale_return.validate()

            for line in return_lines:
                sale_line = lines_by_id[line.sale_line_id]
                await uow.stock.change(
                    sale_line.product_id, sale.warehouse_id, line.quantity.value,
                    sale_line.variant_id,
                )

            await uow.sale_returns.add(sale_return)

            cash_to_client = refund
            if sale.payment_method is PaymentMethod.CREDIT:
                cash_to_client = await self._reduce_debt(uow, sale, refund)

            await uow.audit.add(
                AuditEntry.record(
                    actor, "sale.return", sale_return.id,
                    sale_id=sale.id,
                    refund=str(refund.amount),
                    cash_to_client=str(cash_to_client.amount),
                )
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
            return ReturnSaleResult(
                sale_return=sale_return, refund=refund, cash_to_client=cash_to_client
            )

    @staticmethod
    def _already_returned(returns: list[SaleReturn]) -> dict[int, Decimal]:
        totals: dict[int, Decimal] = {}
        for sale_return in returns:
            for line in sale_return.lines:
                totals[line.sale_line_id] = (
                    totals.get(line.sale_line_id, Decimal("0")) + line.quantity.value
                )
        return totals

    @staticmethod
    async def _reduce_debt(uow: IUnitOfWork, sale: Sale, refund: Money) -> Money:
        """Уменьшает долг по продаже; возвращает сумму, которую нужно отдать клиенту наличными.

        Сначала гасим остаток долга; если возврат больше — разница уходит
        клиенту (он платил часть сразу через paid_now или погашал раньше).
        """
        debt = next(
            (d for d in await uow.debts.list_by_client(sale.client_id) if d.sale_id == sale.id),
            None,
        )
        if debt is None:
            return refund
        reduction = refund if refund < debt.balance else debt.balance
        if reduction > Money.zero():
            debt.repay(reduction, date.today())
            await uow.debts.save(debt)
        return refund - reduction
