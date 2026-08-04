from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity


class StockDocType(StrEnum):
    RECEIPT = "receipt"        # приёмка
    WRITE_OFF = "write_off"    # списание
    TRANSFER = "transfer"      # перемещение
    STOCKTAKE = "stocktake"    # инвентаризация


@dataclass
class StockLine:
    product_id: int
    quantity: Quantity
    variant_id: int | None = None
    cost: Money | None = None  # закупочная цена (для приёмки)


@dataclass
class StockDocument:
    """Остаток меняется только проведением документа."""

    id: int | None
    type: StockDocType
    warehouse_id: int
    author_id: int
    lines: list[StockLine] = field(default_factory=list)
    to_warehouse_id: int | None = None  # для перемещения
    note: str = ""
    posted: bool = False

    def post(self) -> None:
        if self.posted:
            raise DomainError("Документ уже проведён")
        if not self.lines:
            raise DomainError("Документ без позиций")
        if self.type is StockDocType.TRANSFER and self.to_warehouse_id is None:
            raise DomainError("Для перемещения нужен склад-получатель")
        self.posted = True


@dataclass
class StockItem:
    """Текущий остаток позиции на складе."""

    product_id: int
    warehouse_id: int
    quantity: Decimal
    variant_id: int | None = None
