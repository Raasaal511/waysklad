from dataclasses import dataclass
from datetime import datetime

from app.domain.identity.permissions import Actor


@dataclass(frozen=True)
class AuditEntry:
    """Запись журнала действий: кто что продал, удалил, изменил — защита от недостач."""

    user_id: int
    action: str  # "sale.create", "debt.repay", "stock.write_off"…
    entity: str  # "sale", "debt", "stock"…
    entity_id: int | None
    details: dict
    id: int | None = None
    created_at: datetime | None = None

    @classmethod
    def record(
        cls, actor: Actor, action: str, entity_id: int | None = None, **details
    ) -> "AuditEntry":
        return cls(
            user_id=actor.id,
            action=action,
            entity=action.split(".")[0],
            entity_id=entity_id,
            details=details,
        )
