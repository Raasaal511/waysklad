from app.domain.common.quantity import Quantity, Unit
from app.domain.tasks.entities import Task
from app.infrastructure.db.models.tasks import TaskModel


class TaskMapper:
    @staticmethod
    def to_orm(task: Task, tenant_id: int, number: int) -> TaskModel:
        return TaskModel(
            tenant_id=tenant_id,
            number=number,
            title=task.title,
            type=task.type,
            status=task.status,
            assigned_user_id=task.assigned_user_id,
            created_by_id=task.created_by_id,
            note=task.note,
            due_date=task.due_date,
            product_id=task.product_id,
            warehouse_id=task.warehouse_id,
            quantity=task.quantity.value if task.quantity is not None else None,
            completed_at=task.completed_at,
        )

    @staticmethod
    def to_entity(
        model: TaskModel,
        unit: Unit | None = None,
        assigned_user_name: str | None = None,
        created_by_name: str | None = None,
    ) -> Task:
        return Task(
            id=model.id,
            title=model.title,
            type=model.type,
            status=model.status,
            assigned_user_id=model.assigned_user_id,
            created_by_id=model.created_by_id,
            note=model.note,
            due_date=model.due_date,
            product_id=model.product_id,
            warehouse_id=model.warehouse_id,
            quantity=Quantity(model.quantity, unit) if model.quantity is not None and unit else None,
            number=model.number,
            created_at=model.created_at,
            completed_at=model.completed_at,
            assigned_user_name=assigned_user_name,
            created_by_name=created_by_name,
        )
