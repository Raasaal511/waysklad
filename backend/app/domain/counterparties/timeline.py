from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum

from app.domain.common.money import Money


class TimelineEventType(StrEnum):
    """Бизнес-события клиента для единой ленты — не сырые audit-коды,
    а то, что понятно владельцу без знания внутренней механики."""

    SALE = "sale"
    ORDER_CREATED = "order_created"
    ORDER_STATUS = "order_status"
    DEBT_ISSUED = "debt_issued"
    DEBT_REPAID = "debt_repaid"
    DEBT_EXTENDED = "debt_extended"
    TASK = "task"


@dataclass(frozen=True)
class ClientTimelineEvent:
    type: TimelineEventType
    occurred_at: datetime
    entity_id: int  # id продажи/заказа/долга/задачи — для перехода на карточку
    title: str  # человекочитаемая подпись, готовая к показу без доработки на фронте
    amount: Money | None = None
    status: str | None = None  # например, order.status.value / task.status.value

    @property
    def sort_key(self) -> tuple[datetime, int]:
        # при равном occurred_at (типично для date-only событий типа выдачи
        # долга) стабильный порядок по entity_id, а не произвольный от sort()
        return (self.occurred_at, self.entity_id)


def at_midnight(d: date) -> datetime:
    """Date-only событие (выдача/погашение долга) как datetime — для единой
    сортировки с datetime-событиями (Sale/Task.created_at приходят из БД как
    timezone-aware UTC, поэтому и здесь возвращаем aware, иначе sort() падает
    на сравнении naive/aware)."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
