from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import func, select, update

from app.domain.common.exceptions import NotFoundError
from app.domain.notifications.entities import Notification, NotificationKind
from app.domain.notifications.repository import INotificationRepository
from app.infrastructure.db.mappers.notifications import NotificationMapper
from app.infrastructure.db.models.notifications import NotificationModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyNotificationRepository(SqlAlchemyRepository, INotificationRepository):
    async def add(self, notification: Notification) -> Notification:
        model = NotificationMapper.to_orm(notification, self._tenant)
        self._session.add(model)
        await self._session.flush()
        notification.id = model.id
        notification.created_at = model.created_at
        return notification

    async def get(self, notification_id: int) -> Notification:
        model = await self._get_model(notification_id)
        return NotificationMapper.to_entity(model)

    async def save(self, notification: Notification) -> Notification:
        model = await self._get_model(notification.id)
        model.is_read = notification.is_read
        await self._session.flush()
        return notification

    async def list_for_user(self, user_id: int, limit: int = 30) -> list[Notification]:
        models = (
            await self._session.execute(
                select(NotificationModel)
                .where(
                    NotificationModel.tenant_id == self._tenant,
                    NotificationModel.user_id == user_id,
                )
                .order_by(NotificationModel.id.desc())
                .limit(limit)
            )
        ).scalars().all()
        return [NotificationMapper.to_entity(m) for m in models]

    async def unread_count(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(NotificationModel).where(
            NotificationModel.tenant_id == self._tenant,
            NotificationModel.user_id == user_id,
            NotificationModel.is_read.is_(False),
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def mark_all_read(self, user_id: int) -> int:
        result = await self._session.execute(
            update(NotificationModel)
            .where(
                NotificationModel.tenant_id == self._tenant,
                NotificationModel.user_id == user_id,
                NotificationModel.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await self._session.flush()
        return result.rowcount or 0

    async def exists_for_entity_on(
        self, user_id: int, kind: NotificationKind, entity_id: int, on: date
    ) -> bool:
        day_start = datetime.combine(on, time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(on, time.max, tzinfo=timezone.utc)
        stmt = select(func.count()).select_from(NotificationModel).where(
            NotificationModel.tenant_id == self._tenant,
            NotificationModel.user_id == user_id,
            NotificationModel.kind == kind,
            NotificationModel.entity_id == entity_id,
            NotificationModel.created_at >= day_start,
            NotificationModel.created_at <= day_end,
        )
        return (await self._session.execute(stmt)).scalar_one() > 0

    async def last_snapshot_value(
        self, user_id: int, kind: NotificationKind, entity_id: int
    ) -> Decimal | None:
        stmt = (
            select(NotificationModel.snapshot_value)
            .where(
                NotificationModel.tenant_id == self._tenant,
                NotificationModel.user_id == user_id,
                NotificationModel.kind == kind,
                NotificationModel.entity_id == entity_id,
            )
            .order_by(NotificationModel.id.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _get_model(self, notification_id: int) -> NotificationModel:
        model = (
            await self._session.execute(
                select(NotificationModel).where(
                    NotificationModel.tenant_id == self._tenant,
                    NotificationModel.id == notification_id,
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Уведомление {notification_id} не найдено")
        return model
