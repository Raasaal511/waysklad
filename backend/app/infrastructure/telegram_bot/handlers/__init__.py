from aiogram import Router

from app.infrastructure.telegram_bot.handlers import catalog, checkout, product, start

router = Router(name="storefront_bot")
router.include_router(start.router)
router.include_router(catalog.router)
router.include_router(product.router)
router.include_router(checkout.router)
