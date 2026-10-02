from aiogram import Router
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
from app.infrastructure.telegram_bot.keyboards import catalog_keyboard
from app.infrastructure.telegram_bot.states import StorefrontFlow

router = Router(name="start")

_LOGIN_LINK_PREFIX = "login_"


async def _confirm_login(token: str, chat_id: int, message: Message, session_factory) -> None:
    uow = SqlAlchemyUnitOfWork(None, session_factory=session_factory)
    try:
        await ConfirmCustomerLoginLinkUseCase(uow).execute(
            ConfirmCustomerLoginLinkCommand(token=token, telegram_chat_id=str(chat_id))
        )
    except DomainError as exc:
        await message.answer(
            f"Не удалось подтвердить номер: {exc}. Вернитесь на сайт и запросите ссылку заново."
        )
        return
    await message.answer(
        "Номер подтверждён. Вернитесь на сайт — можно продолжить.\n\n"
        "Если запрашивали код в профиле: дождитесь сообщения с кодом или "
        "отправьте его командой /confirm 123456."
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
        await _confirm_login(token, message.chat.id, message, session_factory)
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
