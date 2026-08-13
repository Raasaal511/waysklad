from app.domain.audit.entities import AuditEntry
from app.infrastructure.db.models.audit import AuditLogModel


class AuditMapper:
    @staticmethod
    def to_orm(entry: AuditEntry, tenant_id: int) -> AuditLogModel:
        return AuditLogModel(
            tenant_id=tenant_id,
            user_id=entry.user_id,
            action=entry.action,
            entity=entry.entity,
            entity_id=entry.entity_id,
            details=entry.details,
        )

    @staticmethod
    def to_entity(model: AuditLogModel, user_name: str | None = None) -> AuditEntry:
        return AuditEntry(
            id=model.id,
            user_id=model.user_id,
            action=model.action,
            entity=model.entity,
            entity_id=model.entity_id,
            details=model.details,
            created_at=model.created_at,
            user_name=user_name,
        )
