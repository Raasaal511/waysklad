"""Смена номера покупателя: ссылка из профиля → бот просит контакт.

Отдельный роутер по той же причине, что и customer_login: обработчик «ждём
контакт» ловит любое сообщение в своём состоянии и внутри одного роутера
перехватил бы /start. Подключается после start.router.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.customers.change_phone import (
    ConfirmCustomerPhoneChangeCommand,
    ConfirmCustomerPhoneChangeUseCase,
)
from app.domain.common.exceptions import DomainError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.telegram_bot.handlers.contact_prompt import ask_contact
from app.infrastructure.telegram_bot.keyboards import owner_contact_keyboard, remove_keyboard
from app.infrastructure.telegram_bot.states import CustomerPhoneChangeFlow

router = Router(name="customer_phone_change")

PHONE_CHANGE_PREFIX = "chphone_"


async def start_phone_change(token: str, message: Message, state: FSMContext) -> None:
    await ask_contact(
        message,
        state,
        CustomerPhoneChangeFlow.waiting_contact,
        "phone_change_token",
        token,
        "Подтвердите новый номер: нажмите кнопку «📱 Поделиться номером» внизу.\n\n"
        "Важно: сделать это нужно из того Telegram, на который оформлен "
        "новый номер — иначе мы не сможем убедиться, что он ваш.",
    )


@router.message(CustomerPhoneChangeFlow.waiting_contact, F.contact)
async def phone_change_contact(message: Message, state: FSMContext, session_factory) -> None:
    token = (await state.get_data()).get("phone_change_token")
    contact = message.contact
    if not token or contact is None or message.from_user is None:
        await state.clear()
        await message.answer("Откройте ссылку из профиля ещё раз.", reply_markup=remove_keyboard())
        return

    uow = SqlAlchemyUnitOfWork(None, session_factory=session_factory)
    try:
        await ConfirmCustomerPhoneChangeUseCase(uow).execute(
            ConfirmCustomerPhoneChangeCommand(
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
        "Номер изменён ✅ Вернитесь на сайт — профиль уже обновлён.",
        reply_markup=remove_keyboard(),
    )


@router.message(CustomerPhoneChangeFlow.waiting_contact)
async def phone_change_waiting_contact(message: Message) -> None:
    await message.answer(
        "Нужна кнопка «📱 Поделиться номером» внизу экрана — набирать номер вручную не нужно.\n"
        "Если кнопки не видно, нажмите значок клавиатуры ⌨️ рядом с полем ввода.",
        reply_markup=owner_contact_keyboard(),
    )
