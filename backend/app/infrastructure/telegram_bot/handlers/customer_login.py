"""Вход и регистрация покупателя: по ссылке с сайта бот просит контакт.

Отдельный роутер, а не часть start.py: обработчик «ждём контакт» ловит любое
сообщение в своём состоянии, и внутри одного роутера он перехватывал бы
/start — покупатель, открывший каталог вместо кнопки, застревал бы навсегда.
Этот роутер подключается после start.router (см. handlers/__init__.py)."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.customers.confirm_login_link import (
    ConfirmCustomerLoginLinkCommand,
    ConfirmCustomerLoginLinkUseCase,
)
from app.domain.common.exceptions import DomainError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.telegram_bot.handlers.contact_prompt import (
    ask_contact as prompt_for_contact,
)
from app.infrastructure.telegram_bot.keyboards import owner_contact_keyboard, remove_keyboard
from app.infrastructure.telegram_bot.states import CustomerLoginFlow

router = Router(name="customer_login")

LOGIN_LINK_PREFIX = "login_"


async def ask_contact(token: str, message: Message, state: FSMContext) -> None:
    await prompt_for_contact(
        message,
        state,
        CustomerLoginFlow.waiting_contact,
        "login_token",
        token,
        "Остался один шаг: нажмите кнопку «📱 Поделиться номером» внизу — "
        "Telegram передаст номер вашего аккаунта, и вход на сайте будет готов.\n\n"
        "Номер нужен магазину, чтобы связаться с вами по заказу.",
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
