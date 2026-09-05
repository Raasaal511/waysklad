from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.inventory.entities import StockDocType
from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin

StockDocTypeColumn = SAEnum(
    StockDocType, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
)


class StockItemModel(Base, TenantMixin):
    """Текущий остаток. Меняется только проведением документа или продажей/возвратом."""

    __tablename__ = "stock_items"
    __table_args__ = (
        # уникальность позиции: NULL-вариант в Postgres не сравнивается, поэтому два частичных индекса
        Index(
            "uq_stock_item_no_variant",
            "tenant_id", "product_id", "warehouse_id",
            unique=True,
            postgresql_where=text("variant_id IS NULL"),
        ),
        Index(
            "uq_stock_item_variant",
            "tenant_id", "product_id", "variant_id", "warehouse_id",
            unique=True,
            postgresql_where=text("variant_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    reserved: Mapped[Decimal] = mapped_column(Numeric(14, 3), server_default="0", default=0)


class StockDocumentModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "stock_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number"),
        # идемпотентность офлайн-очереди (приёмка/списание); документы других типов
        # (перемещение/инвентаризация) в sync не участвуют — client_op_id у них NULL
        UniqueConstraint("tenant_id", "client_op_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int]  # сквозной номер в пределах магазина
    type: Mapped[StockDocType] = mapped_column(StockDocTypeColumn)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    to_warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))  # перемещение
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))  # приёмка
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(Text, default="")
    posted: Mapped[bool] = mapped_column(default=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_op_id: Mapped[str | None] = mapped_column(String(64))

    lines: Mapped[list["StockDocumentLineModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class StockDocumentLineModel(Base, TenantMixin):
    __tablename__ = "stock_document_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("stock_documents.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # закупочная цена (для приёмки)
