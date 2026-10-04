"""Общий шаг «попроси контакт кнопкой» для всех сценариев подтверждения.

Вход покупателя, смена номера и привязка владельца начинаются одинаково:
сбросить состояние, запомнить токен, показать клавиатуру с «Поделиться
номером». Отличается только текст — он и остаётся параметром.
"""

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message

from app.infrastructure.telegram_bot.keyboards import owner_contact_keyboard


async def ask_contact(
    message: Message,
    state: FSMContext,
    waiting_state: State,
    token_key: str,
    token: str,
    text: str,
) -> None:
    """Номер просим кнопкой: вписать его в Telegram руками нельзя, значит
    подтверждение нельзя подделать (см. check_telegram_contact).

    Токен кладём в состояние, чтобы контакт относился именно к той ссылке,
    по которой пришли."""
    await state.clear()
    await state.set_state(waiting_state)
    await state.update_data(**{token_key: token})
    await message.answer(text, reply_markup=owner_contact_keyboard())
