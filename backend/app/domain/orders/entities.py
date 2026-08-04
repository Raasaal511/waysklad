from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity


class OrderStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    ISSUED = "issued"


_ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.IN_PROGRESS, OrderStatus.READY},
    OrderStatus.IN_PROGRESS: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.ISSUED},
    OrderStatus.ISSUED: set(),
}


@dataclass
class OrderLine:
    product_id: int
    quantity: Quantity
    price: Money
    variant_id: int | None = None

    @property
    def total(self) -> Money:
        return self.price * self.quantity.value


@dataclass
class Order:
    """Заказ клиента (Instagram/WhatsApp-торговля): предоплата, дата готовности."""

    id: int | None
    client_id: int
    lines: list[OrderLine] = field(default_factory=list)
    due_date: date | None = None
    prepayment: Money = field(default_factory=Money.zero)
    status: OrderStatus = OrderStatus.NEW
    note: str = ""

    @property
    def total(self) -> Money:
        total = Money.zero()
        for line in self.lines:
            total = total + line.total
        return total

    @property
    def to_pay(self) -> Money:
        """Доплата при выдаче."""
        return self.total - self.prepayment

    def change_status(self, new: OrderStatus) -> None:
        if new not in _ALLOWED[self.status]:
            raise DomainError(f"Нельзя перевести заказ из «{self.status}» в «{new}»")
        self.status = new
