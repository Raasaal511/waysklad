from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.application.tasks.change_status import ChangeTaskStatusCommand
from app.application.tasks.create_task import CreateTaskCommand
from app.domain.tasks.entities import Task, TaskStatus, TaskType


class TaskCreateRequest(BaseModel):
    title: str
    type: TaskType = TaskType.GENERAL
    assigned_user_id: int | None = None
    note: str = ""
    due_date: date | None = None
    product_id: int | None = None
    warehouse_id: int | None = None
    quantity: Decimal | None = None

    def to_command(self) -> CreateTaskCommand:
        return CreateTaskCommand(
            title=self.title,
            type=self.type,
            assigned_user_id=self.assigned_user_id,
            note=self.note,
            due_date=self.due_date,
            product_id=self.product_id,
            warehouse_id=self.warehouse_id,
            quantity=self.quantity,
        )


class ChangeTaskStatusRequest(BaseModel):
    new_status: TaskStatus

    def to_command(self, task_id: int) -> ChangeTaskStatusCommand:
        return ChangeTaskStatusCommand(task_id=task_id, new_status=self.new_status)


class TaskResponse(BaseModel):
    id: int
    number: int | None
    title: str
    type: TaskType
    status: TaskStatus
    assigned_user_id: int | None
    assigned_user_name: str | None
    created_by_id: int | None
    created_by_name: str | None
    note: str
    due_date: date | None
    product_id: int | None
    warehouse_id: int | None
    quantity: Decimal | None
    created_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_entity(cls, task: Task) -> "TaskResponse":
        return cls(
            id=task.id,
            number=task.number,
            title=task.title,
            type=task.type,
            status=task.status,
            assigned_user_id=task.assigned_user_id,
            assigned_user_name=task.assigned_user_name,
            created_by_id=task.created_by_id,
            created_by_name=task.created_by_name,
            note=task.note,
            due_date=task.due_date,
            product_id=task.product_id,
            warehouse_id=task.warehouse_id,
            quantity=task.quantity.value if task.quantity is not None else None,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )
