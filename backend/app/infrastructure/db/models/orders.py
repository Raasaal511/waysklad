from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.orders.entities import OrderSource, OrderStatus
from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin

OrderStatusColumn = SAEnum(
    OrderStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
)
OrderSourceColumn = SAEnum(
    OrderSource, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
)


class OrderModel(Base, TenantMixin, TimestampMixin):
    """Заказ клиента (Instagram/WhatsApp-торговля)."""

    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("tenant_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int]
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    status: Mapped[OrderStatus] = mapped_column(OrderStatusColumn, default=OrderStatus.NEW)
    source: Mapped[OrderSource] = mapped_column(OrderSourceColumn, default=OrderSource.IN_PERSON)
    due_date: Mapped[date] = mapped_column(Date)  # дата готовности/выдачи
    prepayment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # запись, не платёж
    note: Mapped[str] = mapped_column(Text, default="")
    # use_alter: orders<->sales — циклическая FK-ссылка (продажа знает заказ и наоборот),
    # без use_alter SQLAlchemy не может упорядочить CREATE/DROP TABLE
    sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales.id", use_alter=True, name="fk_orders_sale_id")
    )

    lines: Mapped[list["OrderLineModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class OrderLineModel(Base, TenantMixin):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
