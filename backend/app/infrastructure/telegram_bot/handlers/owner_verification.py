"""Регистрация владельца и привязка Telegram: ссылка с сайта → «Поделиться
номером» → код для сайта. Бизнес-логика — application/auth/telegram_signup.py."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.auth.telegram_signup import (
    AcceptContactUseCase,
    ContactCommand,
    DescribeVerificationUseCase,
    code_message,
)
from app.domain.common.exceptions import DomainError
from app.domain.identity.telegram_verification import ContactCheck, VerificationPurpose
from app.infrastructure.config import settings
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.security import BcryptPasswordHasher
from app.infrastructure.telegram_bot.keyboards import (
    back_to_site_keyboard,
    owner_contact_keyboard,
    remove_keyboard,
)
from app.infrastructure.telegram_bot.states import OwnerVerificationFlow

router = Router(name="owner_verification")

SIGNUP_PREFIX = "reg_"
LINK_PREFIX = "link_"


async def start_owner_verification(message: Message, state: FSMContext, token: str, session_factory) -> None:
    """Вызывается из /start, когда ссылка — регистрация или привязка владельца."""
    try:
        info = await DescribeVerificationUseCase(
            SqlAlchemyUnitOfWork(None, session_factory=session_factory)
        ).execute(token)
    except DomainError as exc:
        await message.answer(f"{exc}.\n\nВернитесь на сайт ВайСклад и получите новую ссылку.", reply_markup=remove_keyboard())
        return

    await state.clear()
    await state.set_state(OwnerVerificationFlow.waiting_contact)
    await state.update_data(verification_token=token)

    if info.purpose is VerificationPurpose.SIGNUP:
        hello = f"Здравствуйте, {info.owner_name}!" if info.owner_name else "Здравствуйте!"
        lead = f"Вы регистрируете магазин «{info.shop_name}» в ВайСклад на номер {info.masked_phone}."
    else:
        hello = "Здравствуйте!"
        lead = f"Подключаем этот Telegram к магазину «{info.shop_name}» (номер {info.masked_phone})."
    await message.answer(
        f"{hello}\n\n{lead}\n\n"
        "Нажмите кнопку «📱 Поделиться номером» внизу — Telegram передаст номер вашего аккаунта, "
        "а мы пришлём код для сайта.\n\n"
        "Номер нужен только для входа и уведомлений магазина.",
        reply_markup=owner_contact_keyboard(),
    )


@router.message(OwnerVerificationFlow.waiting_contact, F.contact)
async def owner_contact(message: Message, state: FSMContext, session_factory) -> None:
    token = (await state.get_data()).get("verification_token")
    contact = message.contact
    if not token or contact is None or message.from_user is None:
        await state.clear()
        await message.answer("Откройте ссылку с сайта ещё раз.", reply_markup=remove_keyboard())
        return

    try:
        result = await AcceptContactUseCase(
            SqlAlchemyUnitOfWork(None, session_factory=session_factory), BcryptPasswordHasher()
        ).execute(
            ContactCommand(
                token=token,
                contact_phone=contact.phone_number,
                contact_user_id=str(contact.user_id or ""),
                sender_user_id=str(message.from_user.id),
                chat_id=str(message.chat.id),
                username=message.from_user.username or "",
            )
        )
    except DomainError as exc:
        await state.clear()
        await message.answer(f"{exc}.\n\nВернитесь на сайт и начните заново.", reply_markup=remove_keyboard())
        return

    if result.check is ContactCheck.NOT_OWN:
        await message.answer(
            "Это чужой контакт. Нажмите кнопку «📱 Поделиться номером» — она отправит номер "
            "именно вашего Telegram.",
            reply_markup=owner_contact_keyboard(),
        )
        return
    if result.check is ContactCheck.PHONE_MISMATCH:
        await message.answer(
            f"Номер этого Telegram не совпадает с указанным на сайте ({result.masked_phone}).\n\n"
            "Исправьте номер в форме на сайте или откройте ссылку из Telegram, "
            "зарегистрированного на этот номер.",
            reply_markup=owner_contact_keyboard(),
        )
        return

    await state.clear()
    await message.answer("Номер подтверждён ✅", reply_markup=remove_keyboard())
    site = settings.public_base_url.rstrip("/")
    # кнопка часто открывает сайт в новой вкладке или браузере Telegram, где шага
    # регистрации нет — токен в ссылке возвращает человека к вводу кода, а не на вход
    back = f"{site}/login?signup={token}" if result.purpose is VerificationPurpose.SIGNUP else site
    await message.answer(
        code_message(result.code or ""),
        reply_markup=back_to_site_keyboard(back) if site.startswith("https://") else None,
    )


@router.message(OwnerVerificationFlow.waiting_contact)
async def owner_waiting_contact(message: Message) -> None:
    """Написали текст вместо кнопки — подсказываем, где она."""
    await message.answer(
        "Нужна кнопка «📱 Поделиться номером» внизу экрана — набирать номер вручную не нужно.\n"
        "Если кнопки не видно, нажмите значок клавиатуры ⌨️ рядом с полем ввода.",
        reply_markup=owner_contact_keyboard(),
    )
