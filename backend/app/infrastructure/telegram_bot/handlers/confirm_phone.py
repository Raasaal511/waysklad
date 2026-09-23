"""Подтверждение телефона кодом из чата с ботом: /confirm 123456 или просто 123456."""

import re

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.application.customers.verify_phone_code import (
    VerifyPhoneCodeCommand,
    VerifyPhoneCodeUseCase,
)
from app.domain.common.exceptions import DomainError, TooManyAttemptsError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

router = Router(name="confirm_phone")

_CODE_RE = re.compile(r"^\d{6}$")


async def _verify_code(chat_id: int, code: str, message: Message, session_factory) -> None:
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as scoped:
        customer = await scoped.customers.get_by_telegram_chat_id(str(chat_id))
    if customer is None:
        await message.answer(
            "Сначала откройте бота по ссылке с сайта (подтверждение номера) "
            "или войдите в аккаунт на витрине и запросите код в профиле."
        )
        return
    if customer.phone_verified:
        await message.answer("Номер уже подтверждён — можно вернуться на сайт.")
        return

    try:
        await VerifyPhoneCodeUseCase(
            SqlAlchemyUnitOfWork(None, session_factory=session_factory)
        ).execute(VerifyPhoneCodeCommand(customer_id=customer.id, code=code))
    except TooManyAttemptsError as exc:
        await message.answer(str(exc))
        return
    except DomainError as exc:
        await message.answer(str(exc))
        return

    await message.answer("Номер подтверждён. Вернитесь на сайт — всё готово.")


@router.message(Command("confirm"))
async def confirm_command(message: Message, command: CommandObject, session_factory) -> None:
    code = (command.args or "").strip()
    if not _CODE_RE.match(code):
        await message.answer(
            "Отправьте код так: /confirm 123456\n"
            "Код приходит сообщением после запроса на сайте (действует 5 минут)."
        )
        return
    await _verify_code(message.chat.id, code, message, session_factory)


@router.message(lambda m: bool(m.text and _CODE_RE.match(m.text.strip())))
async def confirm_plain_code(message: Message, session_factory) -> None:
    code = (message.text or "").strip()
    await _verify_code(message.chat.id, code, message, session_factory)
