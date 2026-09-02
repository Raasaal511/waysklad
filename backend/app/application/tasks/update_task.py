from dataclasses import dataclass
from datetime import date

from app.application.tasks.notify import notify_user
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import AccessDeniedError
from app.domain.common.notifier import INotifier
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.notifications.entities import NotificationKind
from app.domain.tasks.entities import Task, UNSET, Unset

_UNRESTRICTED_ROLES = (Role.OWNER, Role.MANAGER)


@dataclass(frozen=True)
class UpdateTaskCommand:
    task_id: int
    assigned_user_id: int | None | Unset = UNSET
    due_date: date | None | Unset = UNSET
    note: str | Unset = UNSET
    client_id: int | None | Unset = UNSET


class UpdateTaskUseCase:
    def __init__(self, uow: IUnitOfWork, notifier: INotifier | None = None):
        self._uow = uow
        self._notifier = notifier

    async def execute(self, actor: Actor, cmd: UpdateTaskCommand) -> Task:
        require(actor, Permission.TASKS_MANAGE)

        async with self._uow as uow:
            task = await uow.tasks.get(cmd.task_id)
            if (
                actor.role not in _UNRESTRICTED_ROLES
                and task.assigned_user_id != actor.id
                and task.created_by_id != actor.id
            ):
                raise AccessDeniedError("Эта задача вам не назначена")

            reassigning = cmd.assigned_user_id is not UNSET and cmd.assigned_user_id != task.assigned_user_id
            if reassigning and cmd.assigned_user_id is not None and cmd.assigned_user_id != actor.id:
                require(actor, Permission.USERS_MANAGE)  # чужие задачи назначает owner/manager
                await uow.users.get(cmd.assigned_user_id)  # проверка существования

            if cmd.client_id is not UNSET and cmd.client_id is not None:
                await uow.clients.get(cmd.client_id)  # проверка существования + tenant

            task.update_fields(
                assigned_user_id=cmd.assigned_user_id, 
                due_date=cmd.due_date, 
                note=cmd.note,
                client_id=cmd.client_id,
            )
            await uow.tasks.save(task)

            details = {}
            if cmd.assigned_user_id is not UNSET:
                details["assigned_user_id"] = cmd.assigned_user_id
            if cmd.due_date is not UNSET:
                details["due_date"] = str(cmd.due_date) if cmd.due_date else None
            if cmd.note is not UNSET:
                details["note_changed"] = True
            if cmd.client_id is not UNSET:
                details["client_id"] = cmd.client_id
            await uow.audit.add(AuditEntry.record(actor, "task.update", task.id, **details))

            if reassigning and task.assigned_user_id is not None and task.assigned_user_id != actor.id:
                await notify_user(
                    uow, self._notifier,
                    user_id=task.assigned_user_id,
                    kind=NotificationKind.TASK_ASSIGNED,
                    text=f"Вам назначена задача: «{task.title}»",
                    link="/tasks",
                    entity_id=task.id,
                )
            await uow.commit()
            return task
