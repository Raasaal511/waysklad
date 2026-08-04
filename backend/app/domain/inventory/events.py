from dataclasses import dataclass
from decimal import Decimal

from app.domain.common.events import DomainEvent


@dataclass(frozen=True)
class StockBelowMinimum(DomainEvent):
    """Остаток упал ниже минимума — предупреждение «заканчивается»."""

    product_id: int
    warehouse_id: int
    quantity: Decimal
