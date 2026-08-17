from fastapi import APIRouter

from app.domain.common.exceptions import AccessDeniedError
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor, Permission
from app.domain.tasks.entities import Task
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.deps import (
    ActorDep,
    ChangeTaskStatusDep,
    CreateTaskDep,
    UowDep,
)
from app.presentation.deps.auth import require_permission
from app.presentation.tasks.schemas import (
    ChangeTaskStatusRequest,
    TaskCreateRequest,
    TaskResponse,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])
_view = require_permission(Permission.TASKS_VIEW)

_UNRESTRICTED_ROLES = (Role.OWNER, Role.MANAGER)


def _scope(actor: Actor) -> int | None:
    """owner/manager видят все задачи магазина; остальные — только свои."""
    return None if actor.role in _UNRESTRICTED_ROLES else actor.id


def _require_visible(actor: Actor, task: Task) -> None:
    if (
        actor.role not in _UNRESTRICTED_ROLES
        and task.assigned_user_id != actor.id
        and task.created_by_id != actor.id
    ):
        raise AccessDeniedError("Эта задача вам не назначена")


@router.post("", status_code=201)
async def create_task(
    body: TaskCreateRequest, actor: ActorDep, use_case: CreateTaskDep
) -> TaskResponse:
    return TaskResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.patch("/{task_id}/status")
async def change_status(
    task_id: int, body: ChangeTaskStatusRequest, actor: ActorDep, use_case: ChangeTaskStatusDep
) -> TaskResponse:
    return TaskResponse.from_entity(await use_case.execute(actor, body.to_command(task_id)))


@router.get("", dependencies=[_view])
async def list_active_tasks(actor: ActorDep, uow: UowDep) -> list[TaskResponse]:
    async with uow:
        tasks = await uow.tasks.list_active(_scope(actor))
        return [TaskResponse.from_entity(t) for t in tasks]


@router.get("/completed", dependencies=[_view])
async def list_completed_tasks(actor: ActorDep, uow: UowDep) -> list[TaskResponse]:
    async with uow:
        tasks = await uow.tasks.list_completed(_scope(actor))
        return [TaskResponse.from_entity(t) for t in tasks]


@router.get("/{task_id}", dependencies=[_view])
async def get_task(task_id: int, actor: ActorDep, uow: UowDep) -> TaskResponse:
    async with uow:
        task = await uow.tasks.get(task_id)
        _require_visible(actor, task)
        return TaskResponse.from_entity(task)


@router.get("/{task_id}/history", dependencies=[_view])
async def get_task_history(task_id: int, actor: ActorDep, uow: UowDep) -> list[AuditEntryResponse]:
    async with uow:
        task = await uow.tasks.get(task_id)
        _require_visible(actor, task)
        entries = await uow.audit.list_by_entity("task", task_id)
        return [AuditEntryResponse.from_entity(e) for e in entries]
