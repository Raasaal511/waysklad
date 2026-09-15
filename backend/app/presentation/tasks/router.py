from fastapi import APIRouter, Response

from app.domain.identity.permissions import Permission
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.deps import (
    ActorDep,
    ChangeTaskStatusDep,
    CreateTaskDep,
    GetTaskDep,
    GetTaskHistoryDep,
    ListActiveTasksDep,
    ListCompletedTasksDep,
    UpdateTaskDep,
)
from app.presentation.deps.auth import require_permission
from app.presentation.tasks.schemas import (
    ChangeTaskStatusRequest,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])
_view = require_permission(Permission.TASKS_VIEW)


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


@router.patch("/{task_id}")
async def update_task(
    task_id: int, body: TaskUpdateRequest, actor: ActorDep, use_case: UpdateTaskDep
) -> TaskResponse:
    return TaskResponse.from_entity(await use_case.execute(actor, body.to_command(task_id)))


@router.get("", dependencies=[_view])
async def list_active_tasks(actor: ActorDep, use_case: ListActiveTasksDep) -> list[TaskResponse]:
    tasks = await use_case.execute(actor)
    return [TaskResponse.from_entity(t) for t in tasks]


@router.get("/completed", dependencies=[_view])
async def list_completed_tasks(
    response: Response, actor: ActorDep, use_case: ListCompletedTasksDep, limit: int = 50, offset: int = 0
) -> list[TaskResponse]:
    result = await use_case.execute(actor, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(result.total)
    return [TaskResponse.from_entity(t) for t in result.tasks]


@router.get("/{task_id}", dependencies=[_view])
async def get_task(task_id: int, actor: ActorDep, use_case: GetTaskDep) -> TaskResponse:
    return TaskResponse.from_entity(await use_case.execute(actor, task_id))


@router.get("/{task_id}/history", dependencies=[_view])
async def get_task_history(
    task_id: int, actor: ActorDep, use_case: GetTaskHistoryDep
) -> list[AuditEntryResponse]:
    entries = await use_case.execute(actor, task_id)
    return [AuditEntryResponse.from_entity(e) for e in entries]
