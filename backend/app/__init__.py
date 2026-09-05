from fastapi import APIRouter

from app.presentation.analytics.router import router as analytics_router
from app.presentation.auth.router import router as auth_router
from app.presentation.counterparties.router import router as counterparties_router
from app.presentation.debts.router import router as debts_router
from app.presentation.inventory.router import router as inventory_router
from app.presentation.marketplace.router import router as marketplace_router
from app.presentation.notifications.router import router as notifications_router
from app.presentation.orders.router import router as orders_router
from app.presentation.products.router import router as products_router
from app.presentation.sales.router import router as sales_router
from app.presentation.storefront.router import router as storefront_router
from app.presentation.sync.router import router as sync_router
from app.presentation.tasks.router import router as tasks_router

router = APIRouter(prefix="/api")

router.include_router(auth_router)
router.include_router(products_router)
router.include_router(inventory_router)
router.include_router(sales_router)
router.include_router(counterparties_router)
router.include_router(debts_router)
router.include_router(orders_router)
router.include_router(tasks_router)
router.include_router(notifications_router)
router.include_router(analytics_router)
router.include_router(sync_router)
router.include_router(storefront_router)
router.include_router(marketplace_router)
