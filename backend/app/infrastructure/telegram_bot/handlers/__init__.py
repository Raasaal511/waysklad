from aiogram import Router

from app.infrastructure.telegram_bot.handlers import (
    catalog,
    customer_login,
    customer_phone_change,
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
# после start.router: «ждём контакт» ловит любое сообщение в своём состоянии
# и внутри одного роутера перехватил бы /start
router.include_router(customer_login.router)
# по той же причине, что и customer_login: своё состояние «ждём контакт»
router.include_router(customer_phone_change.router)
# перед catalog/checkout — их callback-паттерны не пересекаются с
# "reject_request:", но регистрация раньше делает намерение явным:
# действия владельца имеют приоритет как более специфичный сценарий
router.include_router(owner_actions.router)
router.include_router(catalog.router)
router.include_router(product.router)
router.include_router(checkout.router)
