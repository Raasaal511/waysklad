from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.tasks.notify import notify_user
from app.domain.audit.entities import AuditEntry
from app.domain.common.notifier import INotifier
from app.domain.common.quantity import Quantity
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require, require_warehouse
from app.domain.notifications.entities import NotificationKind
from app.domain.tasks.entities import Task, TaskType


@dataclass(frozen=True)
class CreateTaskCommand:
    title: str
    type: TaskType = TaskType.GENERAL
    assigned_user_id: int | None = None
    note: str = ""
    due_date: date | None = None
    # только для type=RESTOCK
    product_id: int | None = None
    warehouse_id: int | None = None
    quantity: Decimal | None = None


class CreateTaskUseCase:
    def __init__(self, uow: IUnitOfWork, notifier: INotifier | None = None):
        self._uow = uow
        self._notifier = notifier

    async def execute(self, actor: Actor, cmd: CreateTaskCommand) -> Task:
        require(actor, Permission.TASKS_MANAGE)

        async with self._uow as uow:
            if cmd.assigned_user_id is not None and cmd.assigned_user_id != actor.id:
                require(actor, Permission.USERS_MANAGE)  # чужие задачи ставит owner/manager
                await uow.users.get(cmd.assigned_user_id)  # проверка существования

            quantity: Quantity | None = None
            if cmd.product_id is not None:
                product = await uow.products.get(cmd.product_id)
                if cmd.warehouse_id is not None:
                    require_warehouse(actor, cmd.warehouse_id)
                if cmd.quantity is not None:
                    quantity = Quantity(cmd.quantity, product.unit)

            task = await uow.tasks.add(
                Task(
                    id=None,
                    title=cmd.title,
                    type=cmd.type,
                    assigned_user_id=cmd.assigned_user_id,
                    created_by_id=actor.id,
                    note=cmd.note,
                    due_date=cmd.due_date,
                    product_id=cmd.product_id,
                    warehouse_id=cmd.warehouse_id,
                    quantity=quantity,
                )
            )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "task.create", task.id,
                    type=cmd.type.value, assigned_user_id=cmd.assigned_user_id,
                )
            )
            if task.assigned_user_id is not None and task.assigned_user_id != actor.id:
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
