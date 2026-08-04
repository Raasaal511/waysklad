"""Сценарий: владелец (или управляющий) добавляет сотрудника."""

from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import AccessDeniedError, DomainError
from app.domain.common.phone import Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role, User
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.identity.ports import IPasswordHasher


@dataclass(frozen=True)
class CreateEmployeeCommand:
    name: str
    phone: str
    password: str
    role: Role


class CreateEmployeeUseCase:
    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, actor: Actor, cmd: CreateEmployeeCommand) -> User:
        require(actor, Permission.USERS_MANAGE)
        # защита от повышения прав: управляющий не создаёт владельцев и управляющих
        if cmd.role in (Role.OWNER, Role.MANAGER) and actor.role is not Role.OWNER:
            raise AccessDeniedError(
                "Создавать владельцев и управляющих может только владелец"
            )
        if len(cmd.password) < 6:
            raise DomainError("Пароль должен быть не короче 6 символов")
        phone = Phone(cmd.phone)

        async with self._uow as uow:
            if await uow.users.get_by_phone(str(phone)) is not None:
                raise DomainError("Этот телефон уже зарегистрирован")
            employee = await uow.users.add(
                User(
                    id=None,
                    name=cmd.name,
                    phone=phone,
                    role=cmd.role,
                    password_hash=self._hasher.hash(cmd.password),
                )
            )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "user.create", employee.id,
                    name=employee.name, role=employee.role.value,
                )
            )
            await uow.commit()
            return employee
