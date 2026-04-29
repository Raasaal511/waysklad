from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.schemas.invertory_system.products import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from src.curd.invertory_system import products as crd

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductRead)
async def create_product(
    data: ProductCreate, session: AsyncSession = Depends(get_session)
):
    return await crd.create_product(data=data, session=session)


@router.get("", response_model=list[ProductRead])
async def get_prodcuts(session: AsyncSession = Depends(get_session)):
    return await crd.get_products(session=session)


@router.get("/{product_id}", response_model=ProductRead)
async def get_prodcut(product_id: int, session: AsyncSession = Depends(get_session)):
    return await crd.get_product(session=session, product_id=product_id)


@router.put("/{product_id}", response_model=ProductRead)
async def update_prodcut(
    product_id: int,
    update_data: ProductUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await crd.update_product(
        session=session, product_id=product_id, product_update=update_data
    )


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int, session: AsyncSession = Depends(get_session)):
    return await crd.delete_product(session=session, product_id=product_id)
