"""Сценарий: владелец (или управляющий) редактирует сотрудника —
имя, роль, активность, привязку к складам."""

from dataclasses import dataclass

from app.application.auth.employee_warehouses import resolve_warehouse_ids
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import AccessDeniedError, DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role, User, ensure_employee_slot
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.identity.ports import IPasswordHasher


@dataclass(frozen=True)
class UpdateEmployeeCommand:
    user_id: int
    name: str
    role: Role
    is_active: bool
    # None — не менять привязку к складам (например, роль не поменялась);
    # для manager/seller/storekeeper пустой список при >1 складе — ошибка
    warehouse_ids: list[int] | None = None
    # новый пароль от владельца (сотрудник забыл) — None, не менять
    password: str | None = None


class UpdateEmployeeUseCase:
    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, actor: Actor, cmd: UpdateEmployeeCommand) -> User:
        require(actor, Permission.USERS_MANAGE)
        if cmd.role in (Role.OWNER, Role.MANAGER) and actor.role is not Role.OWNER:
            raise AccessDeniedError(
                "Назначать роль владельца и управляющего может только владелец"
            )
        if not cmd.name.strip():
            raise DomainError("Имя не может быть пустым")
        if cmd.password is not None and len(cmd.password) < 6:
            raise DomainError("Пароль должен быть не короче 6 символов")

        async with self._uow as uow:
            employee = await uow.users.get(cmd.user_id)
            if employee.role is Role.OWNER and cmd.role is not Role.OWNER:
                raise DomainError("Нельзя понизить владельца магазина в другую роль")

            # включение отключённого занимает место в лимите так же, как новый
            if cmd.is_active and not employee.is_active and employee.role is not Role.OWNER:
                ensure_employee_slot(await uow.users.list_by_tenant())

            employee.name = cmd.name.strip()
            employee.role = cmd.role
            employee.is_active = cmd.is_active
            if cmd.password is not None:
                employee.password_hash = self._hasher.hash(cmd.password)
                # старые сессии сотрудника закрываются — новый пароль действует сразу
                employee.token_version += 1
            employee = await uow.users.save(employee)

            if cmd.role is Role.OWNER:
                await uow.warehouses.set_user_assignments(employee.id, [])
            elif cmd.warehouse_ids is not None:
                warehouse_ids = await resolve_warehouse_ids(uow, cmd.role, cmd.warehouse_ids)
                await uow.warehouses.set_user_assignments(employee.id, warehouse_ids)

            await uow.audit.add(
                AuditEntry.record(
                    actor, "user.update", employee.id,
                    name=employee.name, role=employee.role.value, is_active=employee.is_active,
                    password_reset=cmd.password is not None,
                )
            )
            await uow.commit()
            return employee
