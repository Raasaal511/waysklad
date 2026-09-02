from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.identity.entities import Role
from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin

# VARCHAR + CHECK вместо нативного PG-enum: добавление роли — простая миграция
RoleColumn = SAEnum(
    Role, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
)


class TenantModel(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    owner_telegram_chat_id: Mapped[str | None] = mapped_column(String(32))  # для сводок бота
    summary_daily_enabled: Mapped[bool] = mapped_column(default=True)
    summary_weekly_enabled: Mapped[bool] = mapped_column(default=False)
    summary_monthly_enabled: Mapped[bool] = mapped_column(default=False)
    summary_daily_hour_msk: Mapped[int] = mapped_column(SmallInteger, default=20)


class WarehouseModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")


class UserModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20), unique=True)  # логин — по телефону
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(RoleColumn, default=Role.SELLER)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Инкрементируется при смене пароля/принудительном разлогине — токены,
    # выданные с прежним значением, перестают проходить проверку (см. get_current_user).
    token_version: Mapped[int] = mapped_column(Integer, default=0)


class WarehouseAssignmentModel(Base):
    """Кто из кладовщиков (storekeeper) отвечает за какой склад — многие-ко-многим."""

    __tablename__ = "warehouse_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
