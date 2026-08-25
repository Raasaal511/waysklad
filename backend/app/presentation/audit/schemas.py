from datetime import datetime

from pydantic import BaseModel

from app.domain.audit.entities import AuditEntry


class AuditEntryResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    action: str
    entity: str
    entity_id: int | None
    details: dict
    created_at: datetime

    @classmethod
    def from_entity(cls, entry: AuditEntry) -> "AuditEntryResponse":
        return cls(
            id=entry.id,
            user_id=entry.user_id,
            user_name=entry.user_name,
            action=entry.action,
            entity=entry.entity,
            entity_id=entry.entity_id,
            details=entry.details,
            created_at=entry.created_at,
        )
