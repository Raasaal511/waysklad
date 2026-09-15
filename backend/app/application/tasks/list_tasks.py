from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor
from app.domain.tasks.entities import Task

_UNRESTRICTED_ROLES = (Role.OWNER, Role.MANAGER)


def _scope(actor: Actor) -> int | None:
    """owner/manager видят все задачи магазина; остальные — только свои."""
    return None if actor.role in _UNRESTRICTED_ROLES else actor.id


class ListActiveTasksUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> list[Task]:
        async with self._uow as uow:
            return await uow.tasks.list_active(_scope(actor))


@dataclass(frozen=True)
class ListCompletedTasksResult:
    tasks: list[Task]
    total: int


class ListCompletedTasksUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, limit: int = 50, offset: int = 0) -> ListCompletedTasksResult:
        async with self._uow as uow:
            tasks, total = await uow.tasks.list_completed(_scope(actor), limit=limit, offset=offset)
            return ListCompletedTasksResult(tasks=tasks, total=total)
