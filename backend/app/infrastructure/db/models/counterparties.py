from decimal import Decimal

from sqlalchemy import Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin


class ClientModel(Base, TenantMixin, TimestampMixin):
    """Клиент — из тетради долгов и контактов телефона."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str] = mapped_column(String(20), default="")
    whatsapp: Mapped[str] = mapped_column(String(20), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    debt_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # NULL — без лимита
    note: Mapped[str] = mapped_column(Text, default="")


class SupplierModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    contact: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(Text, default="")
