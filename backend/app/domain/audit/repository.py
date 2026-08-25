from typing import Protocol

from app.domain.audit.entities import AuditEntry


class IAuditRepository(Protocol):
    async def add(self, entry: AuditEntry) -> AuditEntry: ...
    async def list_by_entity(self, entity: str, entity_id: int) -> list[AuditEntry]: ...
