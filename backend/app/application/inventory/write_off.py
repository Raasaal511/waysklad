from dataclasses import dataclass

from app.application.inventory.common import (
    LineInput,
    build_lines,
    decrease_stock,
    require_warehouse_access,
)
from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.inventory.entities import StockDocType, StockDocument
from app.infrastructure.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class WriteOffCommand:
    warehouse_id: int
    lines: list[LineInput]
    note: str = ""  # причина: порча, усушка, бой…
    client_op_id: str | None = None  # id операции с устройства — идемпотентность офлайн-очереди


class WriteOffUseCase:
    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: WriteOffCommand) -> StockDocument:
        require(actor, Permission.STOCK_WRITE_OFF)

        async with self._uow as uow:
            if cmd.client_op_id is not None:
                existing = await uow.stock_documents.get_by_client_op_id(cmd.client_op_id)
                if existing is not None:
                    return existing

            await require_warehouse_access(uow, actor, cmd.warehouse_id)
            document = StockDocument(
                id=None,
                type=StockDocType.WRITE_OFF,
                warehouse_id=cmd.warehouse_id,
                author_id=actor.id,
                lines=await build_lines(uow, cmd.lines),
                note=cmd.note,
                client_op_id=cmd.client_op_id,
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
            await invalidate_shop_cache(self._cache, uow)
            return document
