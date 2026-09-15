from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import AccessDeniedError, DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import User
from app.domain.identity.permissions import Actor
from app.domain.identity.ports import IPasswordHasher


@dataclass(frozen=True)
class ChangePasswordCommand:
    current_password: str
    new_password: str


class ChangePasswordUseCase:
    """Пользователь меняет свой собственный пароль — доступно любой роли."""

    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, actor: Actor, cmd: ChangePasswordCommand) -> User:
        if len(cmd.new_password) < 6:
            raise DomainError("Пароль должен быть не короче 6 символов")

        async with self._uow as uow:
            user = await uow.users.get(actor.id)
            if not self._hasher.verify(cmd.current_password, user.password_hash):
                raise AccessDeniedError("Текущий пароль указан неверно")
            user.password_hash = self._hasher.hash(cmd.new_password)
            # разлогинивает все остальные устройства/сессии — токены, выданные
            # до смены пароля, больше не проходят проверку token_version
            user.token_version += 1
            saved = await uow.users.save(user)
            await uow.audit.add(AuditEntry.record(actor, "user.change_password", user.id))
            await uow.commit()
            return saved
