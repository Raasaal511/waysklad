"""Обращения из кабинетов (вопрос / ошибка / рекомендация) — вкладка админки.

Кросс-тенантный список, как list_tenants.py: такой запрос живёт только в
admin-модуле, чтобы однажды не попасть в сценарий магазина.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.domain.common.exceptions import NotFoundError
from app.domain.feedback.entities import FeedbackTopic
from app.infrastructure.db.models.feedback import FeedbackModel
from app.infrastructure.db.models.identity import TenantModel, UserModel
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

DEFAULT_LIMIT = 50
STATUSES = ("new", "resolved", "all")


@dataclass(frozen=True)
class FeedbackListItem:
    id: int
    topic: str
    text: str
    photos: list[str]
    page: str
    user_agent: str
    app_version: str
    created_at: datetime
    resolved_at: datetime | None
    tenant_id: int
    shop_name: str
    author_name: str
    author_phone: str
    author_role: str


@dataclass(frozen=True)
class FeedbackListResult:
    items: list[FeedbackListItem]
    total: int
    # для счётчика на вкладке — сколько ещё не разобрано, независимо от фильтра
    new_count: int


async def list_feedback(
    session_factory,
    *,
    topic: str | None = None,
    status: str = "new",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> FeedbackListResult:
    conditions = []
    if topic:
        conditions.append(FeedbackModel.topic == FeedbackTopic(topic).value)
    if status == "new":
        conditions.append(FeedbackModel.resolved_at.is_(None))
    elif status == "resolved":
        conditions.append(FeedbackModel.resolved_at.is_not(None))

    async with session_factory() as session:
        rows = await session.execute(
            select(FeedbackModel, TenantModel.name, UserModel.name, UserModel.phone, UserModel.role)
            .join(TenantModel, TenantModel.id == FeedbackModel.tenant_id)
            .join(UserModel, UserModel.id == FeedbackModel.user_id)
            .where(*conditions)
            .order_by(FeedbackModel.created_at.desc(), FeedbackModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        total = await session.scalar(
            select(func.count()).select_from(FeedbackModel).where(*conditions)
        )
        new_count = await session.scalar(
            select(func.count()).select_from(FeedbackModel).where(FeedbackModel.resolved_at.is_(None))
        )

    items = [
        FeedbackListItem(
            id=model.id,
            topic=model.topic,
            text=model.text,
            photos=list(model.photos or []),
            page=model.page,
            user_agent=model.user_agent,
            app_version=model.app_version,
            created_at=model.created_at,
            resolved_at=model.resolved_at,
            tenant_id=model.tenant_id,
            shop_name=shop_name,
            author_name=author_name,
            author_phone=author_phone,
            author_role=str(getattr(author_role, "value", author_role)),
        )
        for model, shop_name, author_name, author_phone, author_role in rows.all()
    ]
    return FeedbackListResult(items=items, total=int(total or 0), new_count=int(new_count or 0))


async def set_feedback_resolved(session_factory, feedback_id: int, resolved: bool) -> bool:
    """«Разобрано» / «Вернуть в новые». False — обращения нет."""
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        try:
            feedback = await uow.feedback.get(feedback_id)
        except NotFoundError:
            return False
        if resolved:
            feedback.resolve(datetime.now(UTC))
        else:
            feedback.reopen()
        await uow.feedback.save(feedback)
        await uow.commit()
    return True
