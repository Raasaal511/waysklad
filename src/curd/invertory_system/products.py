from fastapi import HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models.inventory_system import Product
from src.schemas.invertory_system.products import ProductCreate, ProductUpdate
from src.exceptions import ProductNotFound


async def create_product(data: ProductCreate, session: AsyncSession):
    exists_product = await session.execute(
        select(Product).where(Product.sku == data.sku)
    )
    if exists_product.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product with this article number already exists",
        )
    new_product = Product(
        name=data.name,
        sku=data.sku,
        barcode=data.barcode,
        purchase_price=data.purchase_price,
        retail_price=data.retail_price,
    )
    session.add(new_product)
    await session.commit()
    await session.refresh(new_product)
    return new_product


async def get_products(session: AsyncSession):
    result = await session.execute(select(Product))
    products = result.scalars().all()
    return products


async def get_product(session: AsyncSession, product_id: int):
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise ProductNotFound()
    return product


async def update_product(
    product_update: ProductUpdate, product_id: int, session: AsyncSession
):

    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise ProductNotFound()
    
    update_data = product_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await session.commit()
    await session.refresh(product)
    return product


async def delete_product(session: AsyncSession, product_id: int):
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise ProductNotFound()
    
    await session.delete(product)
    await session.commit()
