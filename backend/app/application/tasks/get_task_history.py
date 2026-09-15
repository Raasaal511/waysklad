from app.application.tasks.get_task import _require_visible
from app.domain.audit.entities import AuditEntry
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor


class GetTaskHistoryUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, task_id: int) -> list[AuditEntry]:
        async with self._uow as uow:
            task = await uow.tasks.get(task_id)
            _require_visible(actor, task)
            return await uow.audit.list_by_entity("task", task_id)
