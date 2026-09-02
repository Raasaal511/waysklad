from dataclasses import dataclass
from datetime import date

from app.application.inventory.common import LineInput, build_lines, require_warehouse_access
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.inventory.entities import StockDocType, StockDocument


@dataclass(frozen=True)
class ReceiveGoodsCommand:
    warehouse_id: int
    lines: list[LineInput]
    note: str = ""
    supplier_id: int | None = None  # если указан — приёмка считается долгом поставщику
    debt_due_date: date | None = None  # «долг до», обязателен при supplier_id


class ReceiveGoodsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ReceiveGoodsCommand) -> StockDocument:
        require(actor, Permission.STOCK_RECEIVE)
        if cmd.supplier_id is not None and cmd.debt_due_date is None:
            raise DomainError("Для приёмки в долг нужно указать срок «Долг до»")

        async with self._uow as uow:
            await require_warehouse_access(uow, actor, cmd.warehouse_id)
            lines = await build_lines(uow, cmd.lines)
            document = StockDocument(
                id=None,
                type=StockDocType.RECEIPT,
                warehouse_id=cmd.warehouse_id,
                author_id=actor.id,
                lines=lines,
                supplier_id=cmd.supplier_id,
                note=cmd.note,
            )
            document.post()
            await uow.stock_documents.add(document)
            for line in document.lines:
                await uow.stock.change(
                    line.product_id, cmd.warehouse_id, line.quantity.value, line.variant_id
                )

            # закупочная цена товара = цена последней приёмки (по строкам этого
            # документа, в порядке их следования) — иначе маржа/прибыль в
            # аналитике продолжает считаться по устаревшей цене, пока владелец
            # не поправит её вручную в карточке товара
            last_cost_by_product: dict[int, Money] = {}
            for line in document.lines:
                if line.cost is not None:
                    last_cost_by_product[line.product_id] = line.cost
            for product_id, cost in last_cost_by_product.items():
                product = await uow.products.get(product_id)
                if product.purchase_price != cost:
                    product.purchase_price = cost
                    await uow.products.save(product)

            if cmd.supplier_id is not None:
                total = Money.zero()
                for line in lines:
                    if line.cost is not None:
                        total = total + line.cost * line.quantity.value
                if total > Money.zero():
                    supplier = await uow.suppliers.get(cmd.supplier_id)
                    debt = Debt(
                        id=None,
                        supplier_id=supplier.id,
                        amount=total,
                        issued_at=date.today(),
                        due_date=cmd.debt_due_date,
                        receipt_document_id=document.id,
                    )
                    debt.validate()
                    await uow.debts.add(debt)

            await uow.audit.add(
                AuditEntry.record(
                    actor, "stock.receive", document.id,
                    warehouse_id=cmd.warehouse_id, positions=len(document.lines),
                    supplier_id=cmd.supplier_id,
                )
            )
            await uow.commit()
            return document
