from decimal import Decimal

from sqlalchemy import Boolean, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin


class ClientModel(Base, TenantMixin, TimestampMixin):
    """Клиент — из тетради долгов и контактов телефона."""

    __tablename__ = "clients"
    __table_args__ = (
        # телефон уникален в пределах магазина — но только непустой: пустая
        # строка (клиент без телефона) не должна блокировать вторую такую же
        Index(
            "uq_clients_tenant_phone", "tenant_id", "phone",
            unique=True, postgresql_where=text("phone != ''"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str] = mapped_column(String(20), default="")
    whatsapp: Mapped[str] = mapped_column(String(20), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    debt_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # NULL — без лимита
    note: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SupplierModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    contact: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(Text, default="")
