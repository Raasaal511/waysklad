from datetime import datetime
from typing import Protocol

from app.domain.feedback.entities import Feedback


class IFeedbackRepository(Protocol):
    """Обращения платформы. Не привязан к tenant: список читает только
    админка (app/application/admin/feedback.py), магазины его не видят."""

    async def add(self, feedback: Feedback) -> Feedback: ...

    async def get(self, feedback_id: int) -> Feedback: ...

    async def save(self, feedback: Feedback) -> Feedback:
        """Сохраняет только отметку «Разобрано» — текст и фото не меняются."""
        ...

    async def count_recent_by_user(self, user_id: int, since: datetime) -> int:
        """Сколько обращений человек отправил с момента since — защита от спама."""
        ...
