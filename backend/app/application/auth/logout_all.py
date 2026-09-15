from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import User
from app.domain.identity.permissions import Actor


class LogoutAllUseCase:
    """Пользователь разлогинивает себя на всех устройствах/сессиях сразу —
    инкремент token_version делает недействительными все ранее выданные токены,
    включая тот, которым выполнен этот запрос."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> User:
        async with self._uow as uow:
            user = await uow.users.get(actor.id)
            user.token_version += 1
            saved = await uow.users.save(user)
            await uow.audit.add(AuditEntry.record(actor, "user.logout_all", user.id))
            await uow.commit()
            return saved
