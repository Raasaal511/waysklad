from sqlalchemy import select

from app.domain.audit.entities import AuditEntry
from app.domain.audit.repository import IAuditRepository
from app.infrastructure.db.mappers.audit import AuditMapper
from app.infrastructure.db.models.audit import AuditLogModel
from app.infrastructure.db.models.identity import UserModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyAuditRepository(SqlAlchemyRepository, IAuditRepository):
    async def add(self, entry: AuditEntry) -> AuditEntry:
        model = AuditMapper.to_orm(entry, self._tenant)
        self._session.add(model)
        await self._session.flush()
        return AuditMapper.to_entity(model)

    async def list_by_entity(self, entity: str, entity_id: int) -> list[AuditEntry]:
        # join с users — карточка сущности показывает не только "что" произошло,
        # но и "кто" это сделал, а не просто user_id.
        rows = (
            await self._session.execute(
                select(AuditLogModel, UserModel.name)
                .outerjoin(UserModel, UserModel.id == AuditLogModel.user_id)
                .where(
                    AuditLogModel.tenant_id == self._tenant,
                    AuditLogModel.entity == entity,
                    AuditLogModel.entity_id == entity_id,
                )
                .order_by(AuditLogModel.id.desc())
            )
        ).all()
        return [AuditMapper.to_entity(m, user_name) for m, user_name in rows]
