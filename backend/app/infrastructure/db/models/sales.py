from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.sales.payment import PaymentMethod
from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin

PaymentMethodColumn = SAEnum(
    PaymentMethod, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
)


class SaleModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number"),
        # идемпотентность офлайн-очереди: повторная отправка не создаст дубль
        UniqueConstraint("tenant_id", "client_op_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int]
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    payment_method: Mapped[PaymentMethod] = mapped_column(PaymentMethodColumn)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # снимок суммы чека
    client_op_id: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, default="")
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    lines: Mapped[list["SaleLineModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class SaleLineModel(Base, TenantMixin):
    __tablename__ = "sale_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # цена на момент продажи
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # снимок закупочной — для прибыли


class SaleReturnModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "sale_returns"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(Text, default="")

    lines: Mapped[list["SaleReturnLineModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class SaleReturnLineModel(Base, TenantMixin):
    __tablename__ = "sale_return_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("sale_returns.id", ondelete="CASCADE"))
    sale_line_id: Mapped[int] = mapped_column(ForeignKey("sale_lines.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
