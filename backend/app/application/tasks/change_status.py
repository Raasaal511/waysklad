from dataclasses import dataclass

from app.application.tasks.notify import notify_user
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import AccessDeniedError
from app.domain.common.notifier import INotifier
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.notifications.entities import NotificationKind
from app.domain.tasks.entities import Task, TaskStatus

_UNRESTRICTED_ROLES = (Role.OWNER, Role.MANAGER)


@dataclass(frozen=True)
class ChangeTaskStatusCommand:
    task_id: int
    new_status: TaskStatus


class ChangeTaskStatusUseCase:
    def __init__(self, uow: IUnitOfWork, notifier: INotifier | None = None):
        self._uow = uow
        self._notifier = notifier

    async def execute(self, actor: Actor, cmd: ChangeTaskStatusCommand) -> Task:
        require(actor, Permission.TASKS_MANAGE)

        async with self._uow as uow:
            task = await uow.tasks.get(cmd.task_id)
            if (
                actor.role not in _UNRESTRICTED_ROLES
                and task.assigned_user_id != actor.id
                and task.created_by_id != actor.id
            ):
                raise AccessDeniedError("Эта задача вам не назначена")

            task.change_status(cmd.new_status)  # домен проверит допустимость перехода
            await uow.tasks.save(task)
            await uow.audit.add(
                AuditEntry.record(actor, "task.status", task.id, status=cmd.new_status.value)
            )
            if task.is_done and task.created_by_id is not None and task.created_by_id != actor.id:
                author = await uow.users.get(actor.id)
                await notify_user(
                    uow, self._notifier,
                    user_id=task.created_by_id,
                    kind=NotificationKind.TASK_DONE,
                    text=f"{author.name} выполнил(а) задачу «{task.title}»",
                    link="/tasks",
                    entity_id=task.id,
                )
            await uow.commit()
            return task
