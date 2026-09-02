from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Date, Enum as SAEnum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.tasks.entities import TaskStatus, TaskType
from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin

TaskTypeColumn = SAEnum(
    TaskType, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
)
TaskStatusColumn = SAEnum(
    TaskStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
)


class TaskModel(Base, TenantMixin, TimestampMixin):
    """Задача канбан-доски: обычная (CRM/личная) или дозаказ товара."""

    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("tenant_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int]
    title: Mapped[str] = mapped_column(String(300))
    type: Mapped[TaskType] = mapped_column(TaskTypeColumn, default=TaskType.GENERAL)
    status: Mapped[TaskStatus] = mapped_column(TaskStatusColumn, default=TaskStatus.NEW)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date | None] = mapped_column(Date)
    # только для type=RESTOCK — предзаполнение формы Приёмки на фронте
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # привязка к клиенту (CRM) — задача попадает в общую ленту событий клиента
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
