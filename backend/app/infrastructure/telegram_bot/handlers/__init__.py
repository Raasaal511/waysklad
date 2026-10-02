from aiogram import Router

from app.infrastructure.telegram_bot.handlers import (
    catalog,
    checkout,
    owner_actions,
    owner_verification,
    product,
    start,
)

router = Router(name="storefront_bot")
router.include_router(start.router)
# до confirm_phone: в состоянии «ждём контакт» шестизначный текст — не код покупателя
router.include_router(owner_verification.router)
# перед catalog/checkout — их callback-паттерны не пересекаются с
# "reject_request:", но регистрация раньше делает намерение явным:
# действия владельца имеют приоритет как более специфичный сценарий
router.include_router(owner_actions.router)
router.include_router(catalog.router)
router.include_router(product.router)
router.include_router(checkout.router)
