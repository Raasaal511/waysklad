from app.domain.common.exceptions import AccessDeniedError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor
from app.domain.tasks.entities import Task

_UNRESTRICTED_ROLES = (Role.OWNER, Role.MANAGER)


def _require_visible(actor: Actor, task: Task) -> None:
    if (
        actor.role not in _UNRESTRICTED_ROLES
        and task.assigned_user_id != actor.id
        and task.created_by_id != actor.id
    ):
        raise AccessDeniedError("Эта задача вам не назначена")


class GetTaskUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, task_id: int) -> Task:
        async with self._uow as uow:
            task = await uow.tasks.get(task_id)
            _require_visible(actor, task)
            return task
