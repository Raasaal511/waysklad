from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, SmallInteger, String, Text
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
    storefront_enabled: Mapped[bool] = mapped_column(default=False)
    owner_telegram_chat_id: Mapped[str | None] = mapped_column(String(32))  # для сводок бота
    summary_daily_enabled: Mapped[bool] = mapped_column(default=True)
    summary_weekly_enabled: Mapped[bool] = mapped_column(default=False)
    summary_monthly_enabled: Mapped[bool] = mapped_column(default=False)
    summary_daily_hour_msk: Mapped[int] = mapped_column(SmallInteger, default=20)
    is_suspended: Mapped[bool] = mapped_column(default=False)
    city: Mapped[str | None] = mapped_column(String(100))
    is_verified: Mapped[bool] = mapped_column(default=False)
    logo: Mapped[str] = mapped_column(String(500), default="")
    storefront_show_stock_qty: Mapped[bool] = mapped_column(default=False)
    storefront_description: Mapped[str] = mapped_column(String(500), default="")
    contact_phone: Mapped[str] = mapped_column(String(20), default="")
    contact_whatsapp: Mapped[str] = mapped_column(String(20), default="")
    contact_telegram: Mapped[str] = mapped_column(String(32), default="")
    storefront_min_order_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    policy_refund_money: Mapped[str] = mapped_column(Text, default="")
    policy_payment: Mapped[str] = mapped_column(Text, default="")
    policy_delivery: Mapped[str] = mapped_column(Text, default="")
    policy_returns: Mapped[str] = mapped_column(Text, default="")


class WarehouseModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")
    show_on_storefront: Mapped[bool] = mapped_column(default=False)
    photo: Mapped[str] = mapped_column(String(500), default="")


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
    # последний успешный вход — нужен админке платформы, чтобы отличать
    # живой магазин от заброшенного (NULL = ни разу не входил после введения поля)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # последний запрос с действующим токеном (с точностью до LAST_SEEN_STEP):
    # токен живёт неделями, поэтому «вход» не говорит, работает ли человек сейчас
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # согласие на обработку телефона (152-ФЗ); NULL — зарегистрирован до введения поля
    personal_data_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    telegram_user_id: Mapped[str | None] = mapped_column(String(32))
    telegram_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WarehouseAssignmentModel(Base):
    """Кто из кладовщиков (storekeeper) отвечает за какой склад — многие-ко-многим."""

    __tablename__ = "warehouse_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class TelegramVerificationModel(Base):
    """Подтверждение номера через бота — см. domain/identity/telegram_verification.py.
    Без TenantMixin: при регистрации магазина ещё нет."""

    __tablename__ = "telegram_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(16))
    phone: Mapped[str] = mapped_column(String(20))
    # регистрация: данные формы до создания магазина
    shop_name: Mapped[str | None] = mapped_column(String(200))
    owner_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(200))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # подключение из кабинета: кого привязываем
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    telegram_user_id: Mapped[str | None] = mapped_column(String(32))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32))
    telegram_username: Mapped[str] = mapped_column(String(64), default="")
    code_hash: Mapped[str | None] = mapped_column(String(200))
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    code_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
