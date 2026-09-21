import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.common.exceptions import DomainError, TooManyAttemptsError
from app.domain.common.uow import IUnitOfWork
from app.domain.customers.code_sender import IVerificationCodeSender
from app.domain.customers.entities import (
    CODE_LENGTH,
    CODE_MAX_PER_HOUR,
    CODE_RESEND_COOLDOWN,
    CODE_TTL,
    CustomerLoginLink,
    PhoneVerificationCode,
)
from app.infrastructure.config import settings
from app.infrastructure.security import hash_password


@dataclass(frozen=True)
class RequestPhoneCodeCommand:
    customer_id: int


@dataclass(frozen=True)
class RequestPhoneCodeResult:
    sent_via: str
    retry_after: int  # секунд до следующей возможной отправки
    telegram_deep_link: str = ""  # непусто, когда покупателю сначала нужно открыть бота


def _generate_code() -> str:
    """Равномерно случайный код фиксированной длины, включая ведущие нули."""
    return "".join(str(secrets.randbelow(10)) for _ in range(CODE_LENGTH))


class RequestPhoneCodeUseCase:
    """Отправка кода подтверждения на телефон покупателя.

    Телефон берётся из аккаунта, а не из запроса: иначе кодом можно было бы
    засыпать произвольный чужой номер.

    Ограничения (в порядке проверки): не чаще раза в CODE_RESEND_COOLDOWN и
    не больше CODE_MAX_PER_HOUR в час на аккаунт. Старые коды гасятся перед
    выпуском нового — иначе у покупателя одновременно жили бы несколько
    действующих кодов.

    Нет telegram_chat_id — отправлять некуда: возвращаем ссылку на бота,
    чтобы покупатель нажал «Старт», и код не выпускаем (лимит не тратится).
    """

    def __init__(self, uow: IUnitOfWork, sender: IVerificationCodeSender):
        self._uow = uow
        self._sender = sender

    async def execute(self, cmd: RequestPhoneCodeCommand) -> RequestPhoneCodeResult:
        now = datetime.now(timezone.utc)

        async with self._uow as uow:
            customer = await uow.customers.get(cmd.customer_id)
            if customer.phone_verified:
                raise DomainError("Телефон уже подтверждён")

            # покупателя ещё нет в боте — код слать некуда
            if self._sender.name == "telegram" and not customer.telegram_chat_id:
                if not settings.telegram_bot_username_clean:
                    raise DomainError("Подтверждение недоступно: не настроен Telegram-бот")
                link = CustomerLoginLink.create(customer.phone)
                await uow.customer_login_links.add(link)
                await uow.commit()
                deep_link = (
                    f"https://t.me/{settings.telegram_bot_username_clean}"
                    f"?start=login_{link.token}"
                )
                return RequestPhoneCodeResult(
                    sent_via=self._sender.name, retry_after=0, telegram_deep_link=deep_link
                )

            last = await uow.customer_phone_codes.get_last(customer.id)
            if last is not None:
                elapsed = now - last.created_at
                if elapsed < CODE_RESEND_COOLDOWN:
                    retry_after = int((CODE_RESEND_COOLDOWN - elapsed).total_seconds()) + 1
                    raise TooManyAttemptsError(
                        f"Код уже отправлен — повторите через {retry_after} с",
                        retry_after=retry_after,
                    )

            sent_last_hour = await uow.customer_phone_codes.count_since(
                customer.id, now - timedelta(hours=1)
            )
            if sent_last_hour >= CODE_MAX_PER_HOUR:
                raise TooManyAttemptsError(
                    "Слишком много запросов кода — попробуйте через час",
                    retry_after=3600,
                )

            code = _generate_code()
            # гасим прежние коды: действующим должен быть только последний
            await uow.customer_phone_codes.expire_active(customer.id, now)
            await uow.customer_phone_codes.add(
                PhoneVerificationCode.issue(
                    customer_id=customer.id,
                    phone=customer.phone,
                    code_hash=hash_password(code),
                    sent_via=self._sender.name,
                    now=now,
                )
            )
            chat_id = customer.telegram_chat_id
            phone = str(customer.phone)
            await uow.commit()

        # отправка после commit: упавший Telegram не должен оставлять в БД
        # «невыпущенный» код, а повтор покупатель закажет сам
        await self._sender.send(chat_id, phone, code)

        return RequestPhoneCodeResult(
            sent_via=self._sender.name,
            retry_after=int(CODE_RESEND_COOLDOWN.total_seconds()),
        )


__all__ = [
    "CODE_TTL",
    "RequestPhoneCodeCommand",
    "RequestPhoneCodeResult",
    "RequestPhoneCodeUseCase",
]
