from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.storefront.get_catalog import GetStorefrontCatalogCommand, GetStorefrontCatalogUseCase
from app.infrastructure.telegram_bot.formatting import catalog_page_text
from app.infrastructure.telegram_bot.keyboards import catalog_keyboard
from app.infrastructure.telegram_bot.states import StorefrontFlow

router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, state: FSMContext, session_factory) -> None:
    slug = (command.args or "").strip()
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
