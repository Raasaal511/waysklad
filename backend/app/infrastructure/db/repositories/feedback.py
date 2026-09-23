from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common.exceptions import NotFoundError
from app.domain.feedback.entities import Feedback, FeedbackTopic
from app.domain.feedback.repository import IFeedbackRepository
from app.infrastructure.db.models.feedback import FeedbackModel


def _to_entity(model: FeedbackModel) -> Feedback:
    return Feedback(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        topic=FeedbackTopic(model.topic),
        text=model.text,
        photos=list(model.photos or []),
        page=model.page,
        user_agent=model.user_agent,
        app_version=model.app_version,
        created_at=model.created_at,
        resolved_at=model.resolved_at,
    )


class SqlAlchemyFeedbackRepository(IFeedbackRepository):
    """Сессия напрямую, без SqlAlchemyRepository._tenant — обращения читает
    админка платформы поперёк магазинов (тот же принцип, что у platform.py)."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, feedback: Feedback) -> Feedback:
        model = FeedbackModel(
            tenant_id=feedback.tenant_id,
            user_id=feedback.user_id,
            topic=feedback.topic.value,
            text=feedback.text,
            photos=list(feedback.photos),
            page=feedback.page,
            user_agent=feedback.user_agent,
            app_version=feedback.app_version,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model, ["created_at"])
        feedback.id = model.id
        feedback.created_at = model.created_at
        return feedback

    async def get(self, feedback_id: int) -> Feedback:
        model = await self._session.get(FeedbackModel, feedback_id)
        if model is None:
            raise NotFoundError(f"Обращение {feedback_id} не найдено")
        return _to_entity(model)

    async def save(self, feedback: Feedback) -> Feedback:
        model = await self._session.get(FeedbackModel, feedback.id)
        if model is None:
            raise NotFoundError(f"Обращение {feedback.id} не найдено")
        model.resolved_at = feedback.resolved_at
        await self._session.flush()
        return feedback

    async def count_recent_by_user(self, user_id: int, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(FeedbackModel)
            .where(FeedbackModel.user_id == user_id, FeedbackModel.created_at >= since)
        )
        return int(result.scalar_one())
