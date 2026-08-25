from dataclasses import dataclass

from app.domain.common.events import DomainEvent
from app.domain.common.money import Money


@dataclass(frozen=True)
class DebtIssued(DomainEvent):
    debt_id: int
    client_id: int
    amount: Money


@dataclass(frozen=True)
class DebtRepaid(DomainEvent):
    debt_id: int
    amount: Money
    balance: Money
