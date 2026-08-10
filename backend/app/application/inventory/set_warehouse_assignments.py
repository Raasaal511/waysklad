from dataclasses import dataclass, field

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role, Warehouse
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class SetWarehouseAssignmentsCommand:
    warehouse_id: int
    user_ids: list[int] = field(default_factory=list)


class SetWarehouseAssignmentsUseCase:
    """Владелец/управляющий назначает или снимает ответственных за склад."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: SetWarehouseAssignmentsCommand) -> Warehouse:
        require(actor, Permission.WAREHOUSES_MANAGE)

        async with self._uow as uow:
            await uow.warehouses.get(cmd.warehouse_id)  # 404, если чужой/не существует

            for user_id in cmd.user_ids:
                candidate = await uow.users.get(user_id)
                if candidate.role not in (Role.STOREKEEPER, Role.OWNER):
                    raise DomainError(
                        f"«{candidate.name}» не может быть ответственным за склад — "
                        "нужна роль кладовщика или владельца"
                    )

            warehouse = await uow.warehouses.set_assignments(cmd.warehouse_id, cmd.user_ids)
            await uow.audit.add(
                AuditEntry.record(
                    actor, "warehouse.set_assignments", warehouse.id,
                    user_ids=cmd.user_ids,
                )
            )
            await uow.commit()
            return warehouse
