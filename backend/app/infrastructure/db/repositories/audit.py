from sqlalchemy import select

from app.domain.audit.entities import AuditEntry
from app.domain.audit.repository import IAuditRepository
from app.infrastructure.db.mappers.audit import AuditMapper
from app.infrastructure.db.models.audit import AuditLogModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyAuditRepository(SqlAlchemyRepository, IAuditRepository):
    async def add(self, entry: AuditEntry) -> AuditEntry:
        model = AuditMapper.to_orm(entry, self._tenant)
        self._session.add(model)
        await self._session.flush()
        return AuditMapper.to_entity(model)

    async def list_recent(self, limit: int = 100) -> list[AuditEntry]:
        models = (
            await self._session.execute(
                select(AuditLogModel)
                .where(AuditLogModel.tenant_id == self._tenant)
                .order_by(AuditLogModel.id.desc())
                .limit(limit)
            )
        ).scalars().all()
        return [AuditMapper.to_entity(m) for m in models]
