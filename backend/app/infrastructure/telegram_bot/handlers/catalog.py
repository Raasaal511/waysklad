from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.application.storefront.get_catalog import GetStorefrontCatalogCommand, GetStorefrontCatalogUseCase
from app.infrastructure.telegram_bot.formatting import catalog_page_text
from app.infrastructure.telegram_bot.keyboards import catalog_keyboard
from app.infrastructure.telegram_bot.states import StorefrontFlow

router = Router(name="catalog")


@router.callback_query(StorefrontFlow.browsing_catalog, lambda c: c.data.startswith("page:"))
async def paginate(callback: CallbackQuery, state: FSMContext, session_factory) -> None:
    offset = int(callback.data.removeprefix("page:"))
    data = await state.get_data()
    slug = data["slug"]

    result = await GetStorefrontCatalogUseCase(session_factory).execute(
        GetStorefrontCatalogCommand(slug=slug, limit=8, offset=offset)
    )
    if result is None:
        await callback.message.edit_text("Этот магазин сейчас недоступен.")
        await callback.answer()
        return

    await state.update_data(offset=offset)
    await callback.message.edit_text(
        catalog_page_text(result.shop_name, offset, result.total),
        reply_markup=catalog_keyboard(result.products, offset, result.total),
    )
    await callback.answer()
