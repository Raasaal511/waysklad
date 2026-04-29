from fastapi import APIRouter

from src.api.v1.inventory_system.products import router as product_router

router = APIRouter(prefix="/api/v1")

router.include_router(product_router)
