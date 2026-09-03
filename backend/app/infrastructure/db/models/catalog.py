from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import Base, TenantMixin, TimestampMixin


class UnitModel(Base, TenantMixin):
    """Единицы измерения: предустановленные сеются при регистрации магазина, свои добавляет владелец."""

    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(50))
    fractional: Mapped[bool] = mapped_column(default=False)


class CategoryModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))


class ProductModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        # штрихкод уникален в пределах магазина; NULL — товар без штрихкода
        UniqueConstraint("tenant_id", "barcode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    sku: Mapped[str | None] = mapped_column(String(100), index=True)  # артикул
    barcode: Mapped[str | None] = mapped_column(String(32))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    unit_code: Mapped[str] = mapped_column(String(10), default="pcs")
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # видна только владельцу
    retail_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)  # порог «заканчивается»
    photo: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    show_on_storefront: Mapped[bool] = mapped_column(default=False)

    variants: Mapped[list["ProductVariantModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class ProductVariantModel(Base, TenantMixin):
    """Вариант товара: размер/цвет — критично для одежды."""

    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("tenant_id", "barcode"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    size: Mapped[str] = mapped_column(String(50), default="")
    color: Mapped[str] = mapped_column(String(50), default="")
    barcode: Mapped[str | None] = mapped_column(String(32))
