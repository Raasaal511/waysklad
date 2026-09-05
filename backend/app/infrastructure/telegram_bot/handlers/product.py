from decimal import Decimal

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.application.storefront.get_catalog import GetStorefrontCatalogCommand, GetStorefrontCatalogUseCase
from app.application.storefront.get_product import GetStorefrontProductCommand, GetStorefrontProductUseCase
from app.infrastructure.config import settings
from app.infrastructure.telegram_bot.formatting import catalog_page_text, product_card_text, quantity_prompt_text
from app.infrastructure.telegram_bot.keyboards import catalog_keyboard, product_keyboard, quantity_keyboard
from app.infrastructure.telegram_bot.states import StorefrontFlow

router = Router(name="product")


@router.callback_query(StorefrontFlow.browsing_catalog, lambda c: c.data.startswith("product:"))
async def open_product(callback: CallbackQuery, state: FSMContext, session_factory) -> None:
    product_id = int(callback.data.removeprefix("product:"))
    data = await state.get_data()
    slug = data["slug"]

    result = await GetStorefrontProductUseCase(session_factory).execute(
        GetStorefrontProductCommand(slug=slug, product_id=product_id)
    )
    if result is None:
        await callback.answer("Товар не найден или больше не доступен.", show_alert=True)
        return

    await state.update_data(product_id=product_id, product_name=result.product.name)
    await state.set_state(StorefrontFlow.viewing_product)

    text = product_card_text(result.product, result.in_stock)
    keyboard = product_keyboard(product_id)
    photo_url = f"{settings.public_base_url}{result.product.photo}" if (
        settings.public_base_url and result.product.photo
    ) else None
    if photo_url:
        await callback.message.delete()
        await callback.message.answer_photo(photo_url, caption=text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(StorefrontFlow.viewing_product, lambda c: c.data == "page:0")
async def back_to_catalog(callback: CallbackQuery, state: FSMContext, session_factory) -> None:
    data = await state.get_data()
    slug = data["slug"]

    result = await GetStorefrontCatalogUseCase(session_factory).execute(
        GetStorefrontCatalogCommand(slug=slug, limit=8, offset=0)
    )
    if result is None:
        await callback.answer("Этот магазин сейчас недоступен.", show_alert=True)
        return

    await state.update_data(offset=0)
    await state.set_state(StorefrontFlow.browsing_catalog)
    text = catalog_page_text(result.shop_name, 0, result.total)
    keyboard = catalog_keyboard(result.products, 0, result.total)
    # если открывали карточку с фото — предыдущее сообщение было answer_photo,
    # у него нет текста для edit_text; проще всего отправить новое сообщение
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(StorefrontFlow.viewing_product, lambda c: c.data.startswith("order:"))
async def start_order(callback: CallbackQuery, state: FSMContext, session_factory) -> None:
    product_id = int(callback.data.removeprefix("order:"))
    result = await GetStorefrontProductUseCase(session_factory).execute(
        GetStorefrontProductCommand(
            slug=(await state.get_data())["slug"], product_id=product_id
        )
    )
    if result is None:
        await callback.answer("Товар больше не доступен.", show_alert=True)
        return

    min_qty = result.product.storefront_min_qty or Decimal("1")
    step = result.product.storefront_step_qty or Decimal("1")
    await state.update_data(quantity=str(min_qty), step=str(step))
    await state.set_state(StorefrontFlow.entering_quantity)

    text = quantity_prompt_text(result.product.name, min_qty)
    keyboard = quantity_keyboard(min_qty, step)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()
