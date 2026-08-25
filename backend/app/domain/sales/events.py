from dataclasses import dataclass

from app.domain.common.events import DomainEvent
from app.domain.common.money import Money
from app.domain.sales.payment import PaymentMethod


@dataclass(frozen=True)
class SaleCompleted(DomainEvent):
    sale_id: int
    total: Money
    payment_method: PaymentMethod


@dataclass(frozen=True)
class SaleReturned(DomainEvent):
    sale_id: int
