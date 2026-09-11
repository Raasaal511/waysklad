from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse
from app.domain.sales.entities import SaleReturn
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class DeleteSaleCommand:
    sale_id: int


class DeleteSaleUseCase:
    """Удаление продажи целиком: возврат всех непроданных остатков на склад,
    полное аннулирование связанного долга (если продажа была «в долг»), soft-delete записи.

    Не физическое удаление — строка остаётся в БД с deleted_at, чтобы не терять историю
    и не ломать уже сформированную аналитику/аудит за прошлые периоды.
    """

    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: DeleteSaleCommand) -> None:
        require(actor, Permission.SALES_DELETE)

        async with self._uow as uow:
            sale = await uow.sales.get(cmd.sale_id)
            require_warehouse(actor, sale.warehouse_id)
            if sale.deleted_at is not None:
                raise DomainError(f"Продажа {sale.id} уже удалена")

            already_returned = self._already_returned(await uow.sale_returns.list_by_sale(sale.id))
            for line in sale.lines:
                returned = already_returned.get(line.id, Decimal("0"))
                remaining = line.quantity.value - returned
                if remaining > 0:
                    await uow.stock.change(
                        line.product_id, sale.warehouse_id, remaining, line.variant_id
                    )

            if sale.payment_method is PaymentMethod.CREDIT and sale.client_id is not None:
                debt = next(
                    (d for d in await uow.debts.list_by_client(sale.client_id) if d.sale_id == sale.id),
                    None,
                )
                if debt is not None and not debt.is_closed:
                    debt.repay(debt.balance, date.today())
                    await uow.debts.save(debt)

            sale.deleted_at = datetime.now(timezone.utc)
            await uow.sales.save(sale)

            await uow.audit.add(
                AuditEntry.record(actor, "sale.delete", sale.id, total=str(sale.total.amount))
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)

    @staticmethod
    def _already_returned(returns: list[SaleReturn]) -> dict[int, Decimal]:
        totals: dict[int, Decimal] = {}
        for sale_return in returns:
            for line in sale_return.lines:
                totals[line.sale_line_id] = (
                    totals.get(line.sale_line_id, Decimal("0")) + line.quantity.value
                )
        return totals
