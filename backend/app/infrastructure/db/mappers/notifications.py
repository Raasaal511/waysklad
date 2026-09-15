from app.domain.notifications.entities import Notification
from app.infrastructure.db.models.notifications import NotificationModel


class NotificationMapper:
    @staticmethod
    def to_orm(notification: Notification, tenant_id: int) -> NotificationModel:
        return NotificationModel(
            tenant_id=tenant_id,
            user_id=notification.user_id,
            kind=notification.kind,
            text=notification.text,
            link=notification.link,
            entity_id=notification.entity_id,
            snapshot_value=notification.snapshot_value,
            is_read=notification.is_read,
        )

    @staticmethod
    def to_entity(model: NotificationModel) -> Notification:
        return Notification(
            id=model.id,
            user_id=model.user_id,
            kind=model.kind,
            text=model.text,
            link=model.link,
            entity_id=model.entity_id,
            snapshot_value=model.snapshot_value,
            is_read=model.is_read,
            created_at=model.created_at,
        )
