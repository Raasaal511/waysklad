from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity


class OrderStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    ISSUED = "issued"
    CANCELLED = "cancelled"


class OrderSource(StrEnum):
    """Откуда пришёл заказ — «заказ за 30 секунд из переписки»."""

    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    CALL = "call"
    IN_PERSON = "in_person"


_ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    # New/in_progress/ready свободно ходят друг в друга (карточки можно
    # перетаскивать на доске в обе стороны). ISSUED/CANCELLED необратимы;
    # переход в них разрешён домену, но на уровне use case достижим только
    # через выделенные сценарии (IssueOrderUseCase/CancelOrderUseCase) —
    # ChangeOrderStatusUseCase их явно отклоняет.
    OrderStatus.NEW: {OrderStatus.IN_PROGRESS, OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.IN_PROGRESS: {OrderStatus.NEW, OrderStatus.READY, OrderStatus.CANCELLED},
    OrderStatus.READY: {
        OrderStatus.NEW,
        OrderStatus.IN_PROGRESS,
        OrderStatus.ISSUED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.ISSUED: set(),
    OrderStatus.CANCELLED: set(),
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
    warehouse_id: int
    lines: list[OrderLine] = field(default_factory=list)
    due_date: date | None = None
    prepayment: Money = field(default_factory=Money.zero)
    status: OrderStatus = OrderStatus.NEW
    source: OrderSource = OrderSource.IN_PERSON
    note: str = ""
    number: int | None = None  # заполняется репозиторием при add()/чтении, не при создании
    sale_id: int | None = None  # проставляется при выдаче (IssueOrderUseCase)
    created_at: datetime | None = None

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

    def validate(self) -> None:
        if not self.lines:
            raise DomainError("Заказ без позиций")
        if self.due_date is None:
            raise DomainError("Укажите дату готовности заказа")
        if self.prepayment > self.total:
            raise DomainError("Предоплата больше суммы заказа")
