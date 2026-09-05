from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.storefront.create_request import (
    CreateStorefrontRequestCommand,
    CreateStorefrontRequestUseCase,
    StorefrontRequestItemInput,
)
from app.domain.common.exceptions import DomainError
from app.infrastructure.telegram_bot.formatting import confirmation_text, quantity_prompt_text
from app.infrastructure.telegram_bot.keyboards import (
    confirm_keyboard,
    phone_request_keyboard,
    quantity_keyboard,
    remove_keyboard,
)
from app.infrastructure.telegram_bot.states import StorefrontFlow

router = Router(name="checkout")


@router.callback_query(StorefrontFlow.entering_quantity, F.data.in_({"qty:inc", "qty:dec"}))
async def adjust_quantity(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    quantity = Decimal(data["quantity"])
    step = Decimal(data["step"])
    if callback.data == "qty:inc":
        quantity += step
    else:
        new_quantity = quantity - step
        quantity = new_quantity if new_quantity > 0 else quantity
    await state.update_data(quantity=str(quantity))
    await callback.message.edit_text(
        quantity_prompt_text(data["product_name"], quantity),
        reply_markup=quantity_keyboard(quantity, step),
    )
    await callback.answer()


@router.callback_query(StorefrontFlow.entering_quantity, F.data == "qty:confirm")
async def ask_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(StorefrontFlow.entering_phone)
    await callback.message.answer(
        "Оставьте номер телефона, чтобы магазин мог с вами связаться "
        "(или нажмите «Пропустить», если не хотите указывать):",
        reply_markup=phone_request_keyboard(),
    )
    await callback.answer()


@router.message(StorefrontFlow.entering_phone, F.contact)
async def phone_from_contact(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.contact.phone_number)
    await _ask_name(message, state)


@router.message(StorefrontFlow.entering_phone, F.text.lower() == "пропустить")
async def skip_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone="")
    await _ask_name(message, state)


@router.message(StorefrontFlow.entering_phone)
async def phone_as_text(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.text.strip())
    await _ask_name(message, state)


async def _ask_name(message: Message, state: FSMContext) -> None:
    await state.set_state(StorefrontFlow.entering_name)
    await message.answer("Как вас зовут?", reply_markup=remove_keyboard())


@router.message(StorefrontFlow.entering_name)
async def name_entered(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Укажите имя, пожалуйста.")
        return
    await state.update_data(customer_name=name)
    await state.set_state(StorefrontFlow.confirming)

    data = await state.get_data()
    await message.answer(
        confirmation_text(data["product_name"], Decimal(data["quantity"]), name, data.get("phone", "")),
        reply_markup=confirm_keyboard(),
    )


@router.callback_query(StorefrontFlow.confirming, F.data == "confirm:cancel")
async def cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Заявка отменена. Наберите /start, чтобы начать заново.")
    await callback.answer()


@router.callback_query(StorefrontFlow.confirming, F.data == "confirm:yes")
async def confirm(callback: CallbackQuery, state: FSMContext, session_factory) -> None:
    data = await state.get_data()
    use_case = CreateStorefrontRequestUseCase(session_factory)
    try:
        request = await use_case.execute(
            CreateStorefrontRequestCommand(
                slug=data["slug"],
                customer_name=data["customer_name"],
                customer_phone=data.get("phone", ""),
                customer_telegram_chat_id=str(callback.from_user.id),
                items=[
                    StorefrontRequestItemInput(
                        product_id=data["product_id"], quantity=Decimal(data["quantity"])
                    )
                ],
            )
        )
    except DomainError as exc:
        await callback.message.edit_text(f"Не получилось отправить заявку: {exc}")
        await callback.answer()
        return

    if request is None:
        await callback.message.edit_text("Магазин сейчас недоступен — заявка не отправлена.")
        await callback.answer()
        return

    await state.clear()
    await callback.message.edit_text(
        "Заявка отправлена! Магазин свяжется с вами. Наберите /start, чтобы посмотреть каталог снова."
    )
    await callback.answer()
