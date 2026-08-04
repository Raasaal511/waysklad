from datetime import datetime

from pydantic import BaseModel

from app.domain.audit.entities import AuditEntry


class AuditEntryResponse(BaseModel):
    id: int
    user_id: int
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
            action=entry.action,
            entity=entry.entity,
            entity_id=entry.entity_id,
            details=entry.details,
            created_at=entry.created_at,
        )
