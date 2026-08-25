from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NotificationKind(StrEnum):
    TASK_ASSIGNED = "task_assigned"
    TASK_DONE = "task_done"
    DEBT_DUE_SOON = "debt_due_soon"
    DEBT_OVERDUE = "debt_overdue"


@dataclass
class Notification:
    """Личное уведомление пользователя — задачам назначили/выполнили и т.п."""

    id: int | None
    user_id: int
    kind: NotificationKind
    text: str
    link: str = ""
    entity_id: int | None = None
    is_read: bool = False
    created_at: datetime | None = None

    def mark_read(self) -> None:
        self.is_read = True
