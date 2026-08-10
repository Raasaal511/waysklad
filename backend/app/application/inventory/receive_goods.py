from dataclasses import dataclass

from app.application.inventory.common import LineInput, build_lines, require_warehouse_access
from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.inventory.entities import StockDocType, StockDocument


@dataclass(frozen=True)
class ReceiveGoodsCommand:
    warehouse_id: int
    lines: list[LineInput]
    note: str = ""


class ReceiveGoodsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ReceiveGoodsCommand) -> StockDocument:
        require(actor, Permission.STOCK_RECEIVE)

        async with self._uow as uow:
            await require_warehouse_access(uow, actor, cmd.warehouse_id)
            document = StockDocument(
                id=None,
                type=StockDocType.RECEIPT,
                warehouse_id=cmd.warehouse_id,
                author_id=actor.id,
                lines=await build_lines(uow, cmd.lines),
                note=cmd.note,
            )
            document.post()
            await uow.stock_documents.add(document)
            for line in document.lines:
                await uow.stock.change(
                    line.product_id, cmd.warehouse_id, line.quantity.value, line.variant_id
                )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "stock.receive", document.id,
                    warehouse_id=cmd.warehouse_id, positions=len(document.lines),
                )
            )
            await uow.commit()
            return document
