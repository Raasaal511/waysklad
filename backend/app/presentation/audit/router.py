from fastapi import APIRouter

from app.domain.identity.permissions import Permission
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.deps import UowDep
from app.presentation.deps.auth import require_permission

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[require_permission(Permission.AUDIT_VIEW)],
)


@router.get("")
async def list_audit(uow: UowDep, limit: int = 50, offset: int = 0) -> list[AuditEntryResponse]:
    async with uow:
        entries = await uow.audit.list_recent(limit, offset)
        return [AuditEntryResponse.from_entity(e) for e in entries]
