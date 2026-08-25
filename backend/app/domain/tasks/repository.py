from typing import Protocol

from app.domain.tasks.entities import Task


class ITaskRepository(Protocol):
    async def add(self, task: Task) -> Task: ...

    async def save(self, task: Task) -> Task:
        """Обновляет статус, исполнителя, срок, заметку (не тип и не привязку к товару)."""
        ...

    async def get(self, task_id: int) -> Task: ...

    async def list_active(self, participant_id: int | None = None) -> list[Task]:
        """Незавершённые задачи. participant_id=None — все задачи tenant (owner/manager);
        иначе — только где актор назначен исполнителем или является автором."""
        ...

    async def list_completed(self, participant_id: int | None = None) -> list[Task]:
        """Выполненные задачи — история, новые сначала."""
        ...
