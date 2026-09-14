from dataclasses import dataclass
from decimal import Decimal

from app.application.inventory.common import LineInput, build_lines, require_warehouse_access
from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.inventory.entities import StockDocType, StockDocument
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class StocktakeCommand:
    warehouse_id: int
    lines: list[LineInput]  # quantity = фактический остаток после пересчёта
    note: str = ""


@dataclass(frozen=True)
class StocktakeDiscrepancy:
    """Строка акта расхождений."""

    product_id: int
    variant_id: int | None
    expected: Decimal
    actual: Decimal

    @property
    def delta(self) -> Decimal:
        return self.actual - self.expected


@dataclass(frozen=True)
class StocktakeResult:
    document: StockDocument
    discrepancies: list[StocktakeDiscrepancy]


class StocktakeUseCase:
    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: StocktakeCommand) -> StocktakeResult:
        require(actor, Permission.STOCK_TAKE)

        async with self._uow as uow:
            await require_warehouse_access(uow, actor, cmd.warehouse_id)
            document = StockDocument(
                id=None,
                type=StockDocType.STOCKTAKE,
                warehouse_id=cmd.warehouse_id,
                author_id=actor.id,
                lines=await build_lines(uow, cmd.lines),
                note=cmd.note,
            )
            document.post()
            await uow.stock_documents.add(document)

            discrepancies = []
            for line in document.lines:
                expected = await uow.stock.get(
                    line.product_id, cmd.warehouse_id, line.variant_id
                )
                actual = line.quantity.value
                if actual != expected:
                    discrepancies.append(
                        StocktakeDiscrepancy(
                            product_id=line.product_id,
                            variant_id=line.variant_id,
                            expected=expected,
                            actual=actual,
                        )
                    )
                    # остаток выставляется в фактическое значение
                    await uow.stock.change(
                        line.product_id, cmd.warehouse_id, actual - expected, line.variant_id
                    )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "stock.stocktake", document.id,
                    warehouse_id=cmd.warehouse_id, discrepancies=len(discrepancies),
                )
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
            return StocktakeResult(document=document, discrepancies=discrepancies)
