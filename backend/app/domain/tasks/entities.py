from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum

from app.domain.common.exceptions import DomainError
from app.domain.common.quantity import Quantity


class TaskType(StrEnum):
    GENERAL = "general"
    RESTOCK = "restock"


class TaskStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"


_ALLOWED: dict[TaskStatus, set[TaskStatus]] = {
    # New/in_progress свободно ходят друг в друга (карточки можно перетаскивать
    # на доске в обе стороны) — необратим только переход в DONE.
    TaskStatus.NEW: {TaskStatus.IN_PROGRESS, TaskStatus.DONE},
    TaskStatus.IN_PROGRESS: {TaskStatus.NEW, TaskStatus.DONE},
    TaskStatus.DONE: set(),  # терминальный, как ISSUED у заказа
}


@dataclass
class Task:
    """Задача канбан-доски: обычная (CRM/личная) или дозаказ товара."""

    id: int | None
    title: str
    type: TaskType = TaskType.GENERAL
    status: TaskStatus = TaskStatus.NEW
    assigned_user_id: int | None = None
    created_by_id: int | None = None
    note: str = ""
    due_date: date | None = None
    # только для type=RESTOCK — предзаполнение формы Приёмки на фронте
    product_id: int | None = None
    warehouse_id: int | None = None
    quantity: Quantity | None = None
    number: int | None = None  # заполняется репозиторием при add()/чтении, не при создании
    created_at: datetime | None = None
    completed_at: datetime | None = None
    # проставляются при чтении (join с users) — как AuditEntry.user_name
    assigned_user_name: str | None = None
    created_by_name: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise DomainError("У задачи должно быть название")
        if self.type is TaskType.RESTOCK and (self.product_id is None or self.warehouse_id is None):
            raise DomainError("Задача на дозаказ требует товара и склада")

    @property
    def is_done(self) -> bool:
        return self.status is TaskStatus.DONE

    def change_status(self, new: TaskStatus) -> None:
        if new not in _ALLOWED[self.status]:
            raise DomainError(f"Нельзя перевести задачу из «{self.status}» в «{new}»")
        self.status = new
        self.completed_at = datetime.now(timezone.utc) if new is TaskStatus.DONE else None
