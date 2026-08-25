from dataclasses import dataclass, field

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role, Warehouse
from app.domain.identity.permissions import Actor, Permission, require


_ASSIGNABLE_ROLES = (Role.MANAGER, Role.SELLER, Role.STOREKEEPER)


@dataclass(frozen=True)
class CreateWarehouseCommand:
    name: str
    address: str = ""
    # id сотрудников (manager/seller/storekeeper), назначаемых на этот склад
    assigned_user_ids: list[int] = field(default_factory=list)


class CreateWarehouseUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateWarehouseCommand) -> Warehouse:
        require(actor, Permission.WAREHOUSES_MANAGE)

        async with self._uow as uow:
            for user_id in cmd.assigned_user_ids:
                candidate = await uow.users.get(user_id)
                if candidate.role not in _ASSIGNABLE_ROLES:
                    raise DomainError(
                        f"«{candidate.name}» не может быть привязан к складу — "
                        "нужна роль управляющего, продавца или кладовщика"
                    )

            warehouse = await uow.warehouses.add(
                Warehouse(
                    id=None,
                    name=cmd.name,
                    address=cmd.address,
                    assigned_user_ids=cmd.assigned_user_ids,
                )
            )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "warehouse.create", warehouse.id,
                    name=warehouse.name, assigned_user_ids=cmd.assigned_user_ids,
                )
            )
            await uow.commit()
            return warehouse
