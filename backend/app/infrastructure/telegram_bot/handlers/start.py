from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.customers.confirm_login_link import (
    ConfirmCustomerLoginLinkCommand,
    ConfirmCustomerLoginLinkUseCase,
)
from app.application.storefront.get_catalog import GetStorefrontCatalogCommand, GetStorefrontCatalogUseCase
from app.domain.common.exceptions import DomainError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.telegram_bot.formatting import catalog_page_text
from app.infrastructure.telegram_bot.handlers import owner_verification
from app.infrastructure.telegram_bot.keyboards import owner_contact_keyboard, remove_keyboard
from app.infrastructure.telegram_bot.keyboards import catalog_keyboard
from app.infrastructure.telegram_bot.states import CustomerLoginFlow, StorefrontFlow

router = Router(name="start")

_LOGIN_LINK_PREFIX = "login_"


async def _ask_contact(token: str, message: Message, state: FSMContext) -> None:
    """Просим номер кнопкой: вписать его руками в Telegram нельзя, значит
    подтверждение нельзя подделать (см. ConfirmCustomerLoginLinkUseCase)."""
    await state.clear()
    await state.set_state(CustomerLoginFlow.waiting_contact)
    await state.update_data(login_token=token)
    await message.answer(
        "Остался один шаг: нажмите кнопку «📱 Поделиться номером» внизу — "
        "Telegram передаст номер вашего аккаунта, и вход на сайте будет готов.\n\n"
        "Номер нужен магазину, чтобы связаться с вами по заказу.",
        reply_markup=owner_contact_keyboard(),
    )


@router.message(CustomerLoginFlow.waiting_contact, F.contact)
async def customer_contact(message: Message, state: FSMContext, session_factory) -> None:
    token = (await state.get_data()).get("login_token")
    contact = message.contact
    if not token or contact is None or message.from_user is None:
        await state.clear()
        await message.answer("Откройте ссылку с сайта ещё раз.", reply_markup=remove_keyboard())
        return

    uow = SqlAlchemyUnitOfWork(None, session_factory=session_factory)
    try:
        await ConfirmCustomerLoginLinkUseCase(uow).execute(
            ConfirmCustomerLoginLinkCommand(
                token=token,
                telegram_chat_id=str(message.chat.id),
                contact_phone=contact.phone_number,
                contact_user_id=str(contact.user_id or ""),
                sender_user_id=str(message.from_user.id),
            )
        )
    except DomainError as exc:
        # номер не тот или контакт чужой — кнопка нужна снова, состояние держим
        await message.answer(str(exc), reply_markup=owner_contact_keyboard())
        return

    await state.clear()
    await message.answer(
        "Номер подтверждён ✅ Вернитесь на сайт — можно продолжить.",
        reply_markup=remove_keyboard(),
    )


@router.message(CustomerLoginFlow.waiting_contact)
async def customer_waiting_contact(message: Message) -> None:
    await message.answer(
        "Нужна кнопка «📱 Поделиться номером» внизу экрана — набирать номер вручную не нужно.\n"
        "Если кнопки не видно, нажмите значок клавиатуры ⌨️ рядом с полем ввода.",
        reply_markup=owner_contact_keyboard(),
    )


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, state: FSMContext, session_factory) -> None:
    arg = (command.args or "").strip()
    for prefix in (owner_verification.SIGNUP_PREFIX, owner_verification.LINK_PREFIX):
        if arg.startswith(prefix):
            await owner_verification.start_owner_verification(
                message, state, arg[len(prefix):], session_factory
            )
            return
    if arg.startswith(_LOGIN_LINK_PREFIX):
        token = arg[len(_LOGIN_LINK_PREFIX):]
        await _ask_contact(token, message, state)
        return

    slug = arg
    if not slug:
        await message.answer(
            "Это бот-витрина ВайСклад. Чтобы посмотреть каталог магазина, "
            "откройте ссылку, которую дал вам продавец (вида t.me/имя_бота?start=магазин)."
        )
        return

    result = await GetStorefrontCatalogUseCase(session_factory).execute(
        GetStorefrontCatalogCommand(slug=slug, limit=8, offset=0)
    )
    if result is None:
        await message.answer("Этот магазин сейчас недоступен.")
        return

    await state.update_data(slug=slug, offset=0)
    await state.set_state(StorefrontFlow.browsing_catalog)
    await message.answer(
        catalog_page_text(result.shop_name, 0, result.total),
        reply_markup=catalog_keyboard(result.products, 0, result.total),
    )
