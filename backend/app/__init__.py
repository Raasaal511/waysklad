from fastapi import APIRouter

from app.presentation.analytics.router import router as analytics_router
from app.presentation.audit.router import router as audit_router
from app.presentation.auth.router import router as auth_router
from app.presentation.counterparties.router import router as counterparties_router
from app.presentation.debts.router import router as debts_router
from app.presentation.inventory.router import router as inventory_router
from app.presentation.orders.router import router as orders_router
from app.presentation.products.router import router as products_router
from app.presentation.sales.router import router as sales_router
from app.presentation.sync.router import router as sync_router

# общий префикс /api задаётся один раз здесь — в роутерах категорий его нет
router = APIRouter(prefix="/api")

router.include_router(auth_router)
router.include_router(products_router)
router.include_router(inventory_router)
router.include_router(sales_router)
router.include_router(counterparties_router)
router.include_router(debts_router)
router.include_router(orders_router)
router.include_router(analytics_router)
router.include_router(audit_router)
router.include_router(sync_router)
