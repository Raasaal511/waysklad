from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased

from app.domain.common.exceptions import NotFoundError
from app.domain.tasks.entities import Task, TaskStatus
from app.domain.tasks.repository import ITaskRepository
from app.infrastructure.db.mappers.tasks import TaskMapper
from app.infrastructure.db.models.identity import UserModel
from app.infrastructure.db.models.tasks import TaskModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository

_Assignee = aliased(UserModel)
_Author = aliased(UserModel)


class SqlAlchemyTaskRepository(SqlAlchemyRepository, ITaskRepository):
    async def add(self, task: Task) -> Task:
        number = await self._next_number(TaskModel)
        model = TaskMapper.to_orm(task, self._tenant, number)
        self._session.add(model)
        await self._session.flush()
        return await self.get(model.id)  # перечитываем с именами исполнителя/автора

    async def save(self, task: Task) -> Task:
        model = (
            await self._session.execute(
                select(TaskModel).where(
                    TaskModel.tenant_id == self._tenant, TaskModel.id == task.id
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Задача {task.id} не найдена")
        model.status = task.status
        model.assigned_user_id = task.assigned_user_id
        model.due_date = task.due_date
        model.note = task.note
        model.completed_at = task.completed_at
        model.client_id = task.client_id
        await self._session.flush()
        return task

    async def get(self, task_id: int) -> Task:
        row = (await self._session.execute(self._select_with_names().where(
            TaskModel.tenant_id == self._tenant, TaskModel.id == task_id
        ))).first()
        if row is None:
            raise NotFoundError(f"Задача {task_id} не найдена")
        return await self._to_entity(*row)

    async def list_active(self, participant_id: int | None = None) -> list[Task]:
        stmt = self._select_with_names().where(
            TaskModel.tenant_id == self._tenant, TaskModel.status != TaskStatus.DONE
        )
        stmt = self._scope(stmt, participant_id).order_by(
            TaskModel.due_date.nulls_last(), TaskModel.id
        )
        rows = (await self._session.execute(stmt)).all()
        return [await self._to_entity(*row) for row in rows]

    async def list_completed(
        self, participant_id: int | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[Task], int]:
        count_stmt = self._scope(
            select(func.count()).select_from(TaskModel).where(
                TaskModel.tenant_id == self._tenant, TaskModel.status == TaskStatus.DONE
            ),
            participant_id,
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = self._select_with_names().where(
            TaskModel.tenant_id == self._tenant, TaskModel.status == TaskStatus.DONE
        )
        stmt = self._scope(stmt, participant_id).order_by(
            TaskModel.completed_at.desc()
        ).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).all()
        return [await self._to_entity(*row) for row in rows], total

    async def list_by_client(self, client_id: int) -> list[Task]:
        stmt = self._select_with_names().where(
            TaskModel.tenant_id == self._tenant, TaskModel.client_id == client_id
        ).order_by(TaskModel.due_date.nulls_last(), TaskModel.id)
        rows = (await self._session.execute(stmt)).all()
        return [await self._to_entity(*row) for row in rows]

    def _select_with_names(self):
        return (
            select(TaskModel, _Assignee.name, _Author.name)
            .outerjoin(_Assignee, _Assignee.id == TaskModel.assigned_user_id)
            .outerjoin(_Author, _Author.id == TaskModel.created_by_id)
        )

    def _scope(self, stmt, participant_id: int | None):
        if participant_id is None:
            return stmt
        return stmt.where(
            or_(
                TaskModel.assigned_user_id == participant_id,
                TaskModel.created_by_id == participant_id,
            )
        )

    async def _to_entity(self, model: TaskModel, assigned_user_name, created_by_name) -> Task:
        unit = None
        if model.product_id is not None:
            units = await self._product_unit_by_id({model.product_id})
            unit = units.get(model.product_id)
        return TaskMapper.to_entity(model, unit, assigned_user_name, created_by_name)
