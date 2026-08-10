from dataclasses import dataclass

from app.application.inventory.common import (
    LineInput,
    build_lines,
    decrease_stock,
    require_warehouse_access,
)
from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.inventory.entities import StockDocType, StockDocument


@dataclass(frozen=True)
class TransferCommand:
    warehouse_id: int       # откуда
    to_warehouse_id: int    # куда
    lines: list[LineInput]
    note: str = ""


class TransferUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: TransferCommand) -> StockDocument:
        require(actor, Permission.STOCK_TRANSFER)

        async with self._uow as uow:
            await require_warehouse_access(uow, actor, cmd.warehouse_id)
            await require_warehouse_access(uow, actor, cmd.to_warehouse_id)
            document = StockDocument(
                id=None,
                type=StockDocType.TRANSFER,
                warehouse_id=cmd.warehouse_id,
                to_warehouse_id=cmd.to_warehouse_id,
                author_id=actor.id,
                lines=await build_lines(uow, cmd.lines),
                note=cmd.note,
            )
            document.post()
            await uow.stock_documents.add(document)
            for line in document.lines:
                await decrease_stock(uow, cmd.warehouse_id, line)
                await uow.stock.change(
                    line.product_id, cmd.to_warehouse_id, line.quantity.value, line.variant_id
                )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "stock.transfer", document.id,
                    from_warehouse=cmd.warehouse_id, to_warehouse=cmd.to_warehouse_id,
                )
            )
            await uow.commit()
            return document
