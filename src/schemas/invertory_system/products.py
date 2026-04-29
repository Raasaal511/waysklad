from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from decimal import Decimal


class ProductBase(BaseModel):
    name: str
    sku: str
    barcode: str
    purchase_price: Decimal
    retail_price: Decimal


class ProductRead(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    retail_price: Optional[Decimal] = None
