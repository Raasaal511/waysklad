from typing import Protocol

from app.domain.audit.entities import AuditEntry


class IAuditRepository(Protocol):
    async def add(self, entry: AuditEntry) -> AuditEntry: ...
    async def list_recent(self, limit: int = 100) -> list[AuditEntry]: ...
