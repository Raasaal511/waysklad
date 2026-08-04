from dataclasses import dataclass

from app.application.inventory.common import LineInput, build_lines, decrease_stock
from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.inventory.entities import StockDocType, StockDocument


@dataclass(frozen=True)
class WriteOffCommand:
    warehouse_id: int
    lines: list[LineInput]
    note: str = ""  # причина: порча, усушка, бой…


class WriteOffUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: WriteOffCommand) -> StockDocument:
        require(actor, Permission.STOCK_WRITE_OFF)

        async with self._uow as uow:
            document = StockDocument(
                id=None,
                type=StockDocType.WRITE_OFF,
                warehouse_id=cmd.warehouse_id,
                author_id=actor.id,
                lines=await build_lines(uow, cmd.lines),
                note=cmd.note,
            )
            document.post()
            await uow.stock_documents.add(document)
            for line in document.lines:
                await decrease_stock(uow, cmd.warehouse_id, line)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "stock.write_off", document.id,
                    warehouse_id=cmd.warehouse_id, positions=len(document.lines),
                    note=cmd.note,
                )
            )
            await uow.commit()
            return document
