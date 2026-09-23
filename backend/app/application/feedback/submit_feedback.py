from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from html import escape

from app.domain.catalog.ports import IFileStorage
from app.domain.common.exceptions import DomainError
from app.domain.common.notifier import INotifier
from app.domain.common.uow import IUnitOfWork
from app.domain.feedback.entities import Feedback, FeedbackTopic, check_feedback_content
from app.domain.identity.permissions import Actor
from app.infrastructure.config import settings
from app.infrastructure.observability.logging import get_logger

_logger = get_logger(__name__)

# Живой человек за час столько не напишет; больше — это зациклившийся клиент или спам.
_RATE_LIMIT_PER_HOUR = 10

TOPIC_LABELS = {
    FeedbackTopic.QUESTION: "Вопрос",
    FeedbackTopic.BUG: "Ошибка",
    FeedbackTopic.SUGGESTION: "Рекомендация",
}


@dataclass(frozen=True)
class FeedbackPhoto:
    filename: str
    content: bytes


@dataclass(frozen=True)
class SubmitFeedbackCommand:
    topic: str
    text: str = ""
    photos: list[FeedbackPhoto] = field(default_factory=list)
    page: str = ""
    user_agent: str = ""
    app_version: str = ""


@dataclass(frozen=True)
class SubmittedFeedback:
    feedback: Feedback
    shop_name: str
    author_name: str
    author_phone: str


class SubmitFeedbackUseCase:
    """Любой сотрудник магазина (любая роль) пишет в поддержку платформы."""

    def __init__(self, uow: IUnitOfWork, storage: IFileStorage):
        self._uow = uow
        self._storage = storage

    async def execute(self, actor: Actor, cmd: SubmitFeedbackCommand) -> SubmittedFeedback:
        # до записи файлов: отклонённое обращение не должно оставлять фото на диске
        check_feedback_content(cmd.text, len(cmd.photos))

        async with self._uow as uow:
            since = datetime.now(UTC) - timedelta(hours=1)
            if await uow.feedback.count_recent_by_user(actor.id, since) >= _RATE_LIMIT_PER_HOUR:
                raise DomainError("Слишком много обращений за час — попробуйте позже")

            saved_urls: list[str] = []
            try:
                for photo in cmd.photos:
                    saved_urls.append(self._storage.save(photo.filename, photo.content))
                feedback = Feedback.create(
                    tenant_id=uow.tenant_id,
                    user_id=actor.id,
                    topic=cmd.topic,
                    text=cmd.text,
                    photos=saved_urls,
                    page=cmd.page,
                    user_agent=cmd.user_agent,
                    app_version=cmd.app_version,
                )
                await uow.feedback.add(feedback)
                shop = await uow.tenants.get(uow.tenant_id)
                author = await uow.users.get(actor.id)
                await uow.commit()
            except Exception:
                for url in saved_urls:
                    self._storage.delete(url)
                raise

        return SubmittedFeedback(
            feedback=feedback,
            shop_name=shop.name,
            author_name=author.name,
            author_phone=str(author.phone),
        )


def notify_admin_about_feedback(notifier: INotifier | None, submitted: SubmittedFeedback) -> None:
    """Сообщение Расулу в Telegram (тот же чат, что и алерты об ошибках сервера).

    Вызывается фоновой задачей после ответа клиенту: отправка в Telegram
    синхронная и может ждать до 10 секунд — человек не должен этого ждать.
    Сбой отправки обращение не теряет: оно уже в админке.
    """
    if notifier is None or not settings.admin_alert_chat_id or not settings.telegram_bot_token:
        return
    feedback = submitted.feedback
    lines = [
        f"✉️ Обратная связь: <b>{TOPIC_LABELS[feedback.topic]}</b>",
        f"{escape(submitted.shop_name)} · {escape(submitted.author_name)} · {escape(submitted.author_phone)}",
    ]
    if feedback.text:
        text = feedback.text if len(feedback.text) <= 1500 else feedback.text[:1500] + "…"
        lines.append("")
        lines.append(escape(text))
    if feedback.photos:
        lines.append(f"\n📎 Фото: {len(feedback.photos)} — смотрите в админке, вкладка «Обратная связь»")
    try:
        notifier.send(settings.admin_alert_chat_id, "\n".join(lines))
    except Exception:  # noqa: BLE001
        _logger.exception("Не удалось отправить обращение %s в Telegram", feedback.id)
