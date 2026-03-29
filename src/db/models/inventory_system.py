from datetime import datetime

from sqlalchemy import String, Integer, DECIMAL, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base


class Product(Base):
    """Товары"""
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purchase_price: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 2), default=0)
    retail_price: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_onupdate=func.now())
    
    stock_items: Mapped[list["Stock"]] = relationship(back_populates="product")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="product")
    inventories: Mapped[list["Inventory"]] = relationship(back_populates="product")


class Warehouse(Base):
    """Склады"""
    __tablename__ = "warehouses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    stock_items: Mapped[list["Stock"]] = relationship(back_populates="warehouse")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="warehouse")
    inventories: Mapped[list["Inventory"]] = relationship(back_populates="warehouse")


class Stock(Base):
    """Остатки"""
    __tablename__ = "stock"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 3), default=0)
    
    product: Mapped["Product"] = relationship(back_populates="stock_items")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="stock_items")


class Reservation(Base):
    """Резервы"""
    __tablename__ = "reservations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 3))
    order_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="reservations")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="reservations")


class Inventory(Base):
    """Инвентаризация"""
    __tablename__ = "inventories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    expected_quantity: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 3))  # По учету
    actual_quantity: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 3))  # Факт
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="inventories")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="inventories")
