from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.common.exceptions import DomainError

MAX_FEEDBACK_TEXT = 2000
MAX_FEEDBACK_PHOTOS = 3


class FeedbackTopic(StrEnum):
    QUESTION = "question"
    BUG = "bug"
    SUGGESTION = "suggestion"


def check_feedback_content(text: str, photo_count: int) -> str:
    """Пустое обращение не принимаем: нужен текст или хотя бы одно фото.

    Отдельной функцией, а не только в Feedback.create: сценарий проверяет
    содержимое до сохранения фото, чтобы не оставлять на диске файлы
    от обращения, которое всё равно будет отклонено. Возвращает текст без
    пробелов по краям.
    """
    cleaned = text.strip()
    if not cleaned and photo_count == 0:
        raise DomainError("Напишите, что случилось, или прикрепите фото")
    if len(cleaned) > MAX_FEEDBACK_TEXT:
        raise DomainError(f"Описание длиннее {MAX_FEEDBACK_TEXT} символов")
    if photo_count > MAX_FEEDBACK_PHOTOS:
        raise DomainError(f"Можно прикрепить не больше {MAX_FEEDBACK_PHOTOS} фото")
    return cleaned


@dataclass
class Feedback:
    """Обращение из кабинета: вопрос, ошибка или рекомендация — для админки платформы.

    page / user_agent / app_version подставляет приложение само: человеку не
    нужно объяснять, где он был и с какого телефона пишет.
    """

    id: int | None
    tenant_id: int
    user_id: int
    topic: FeedbackTopic
    text: str = ""
    photos: list[str] = field(default_factory=list)
    page: str = ""
    user_agent: str = ""
    app_version: str = ""
    created_at: datetime | None = None
    resolved_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        tenant_id: int,
        user_id: int,
        topic: str,
        text: str,
        photos: list[str],
        page: str = "",
        user_agent: str = "",
        app_version: str = "",
    ) -> Feedback:
        try:
            parsed_topic = FeedbackTopic(topic)
        except ValueError as exc:
            raise DomainError("Выберите тему: вопрос, ошибка или рекомендация") from exc
        cleaned = check_feedback_content(text, len(photos))
        return cls(
            id=None,
            tenant_id=tenant_id,
            user_id=user_id,
            topic=parsed_topic,
            text=cleaned,
            photos=list(photos),
            # служебные поля обрезаем, а не отклоняем: из-за длинного адреса
            # или строки браузера обращение не должно теряться
            page=page[:500],
            user_agent=user_agent[:500],
            app_version=app_version[:50],
        )

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None

    def resolve(self, now: datetime) -> None:
        if self.resolved_at is None:
            self.resolved_at = now

    def reopen(self) -> None:
        self.resolved_at = None
