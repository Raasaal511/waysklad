"""Подтверждение номера владельца через Telegram-бота.

Сайт выдаёт ссылку t.me/<бот>?start=<reg|link>_<token>; бот просит
«Поделиться номером» (Telegram сам отдаёт номер аккаунта — его нельзя
вписать руками), сверяет с указанным на сайте и присылает код, который
человек вводит на сайте. Так в одном шаге проверяются и номер, и то, что
у владельца есть рабочий Telegram для уведомлений.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from app.domain.common.exceptions import DomainError, TooManyAttemptsError
from app.domain.common.phone import Phone

# Сколько живёт ссылка на бота: успеть открыть Telegram, найти кнопку, вернуться.
LINK_TTL = timedelta(minutes=30)
# Код из бота — короче: он уже на экране у человека.
CODE_TTL = timedelta(minutes=10)
MAX_CODE_ATTEMPTS = 5
# Повторный код — не чаще раза в минуту: защита от спама в чат и перебора.
RESEND_COOLDOWN = timedelta(seconds=60)


class VerificationPurpose(StrEnum):
    # новый магазин: данные формы ждут подтверждения, магазин ещё не создан
    SIGNUP = "signup"
    # уже зарегистрированный владелец привязывает Telegram из кабинета
    LINK = "link"


class ContactCheck(StrEnum):
    """Почему бот не принял контакт — у каждого случая свой текст в чате."""

    OK = "ok"
    NOT_OWN = "not_own"  # переслан чужой контакт
    PHONE_MISMATCH = "phone_mismatch"


@dataclass(frozen=True)
class SignupData:
    """Данные формы регистрации — магазин создаётся из них только после кода."""

    shop_name: str
    owner_name: str
    password_hash: str
    consent_at: datetime


@dataclass
class TelegramVerification:
    id: int | None
    token: str
    purpose: VerificationPurpose
    phone: Phone
    expires_at: datetime
    created_at: datetime
    signup: SignupData | None = None
    # для LINK: кого привязываем
    user_id: int | None = None
    tenant_id: int | None = None
    telegram_user_id: str | None = None
    telegram_chat_id: str | None = None
    telegram_username: str = ""
    code_hash: str | None = None
    code_expires_at: datetime | None = None
    code_sent_at: datetime | None = None
    attempts: int = 0
    completed_at: datetime | None = None

    @classmethod
    def start(
        cls,
        purpose: VerificationPurpose,
        phone: Phone,
        now: datetime,
        signup: SignupData | None = None,
        user_id: int | None = None,
        tenant_id: int | None = None,
    ) -> "TelegramVerification":
        if purpose is VerificationPurpose.SIGNUP and signup is None:
            raise DomainError("Нет данных регистрации")
        if purpose is VerificationPurpose.LINK and user_id is None:
            raise DomainError("Не указан пользователь")
        return cls(
            id=None,
            token=secrets.token_urlsafe(24),
            purpose=purpose,
            phone=phone,
            expires_at=now + LINK_TTL,
            created_at=now,
            signup=signup,
            user_id=user_id,
            tenant_id=tenant_id,
        )

    @property
    def contact_confirmed(self) -> bool:
        return self.code_hash is not None

    def ensure_active(self, now: datetime) -> None:
        if self.completed_at is not None:
            raise DomainError("Номер уже подтверждён")
        if now >= self.expires_at:
            raise DomainError("Ссылка устарела — начните заново")

    def check_contact(self, contact_phone: str, contact_user_id: str, sender_user_id: str) -> ContactCheck:
        """Свой ли это контакт и тот ли номер, что указан на сайте.

        Telegram даёт номер без «+», в международном формате — приводим к E.164."""
        if contact_user_id != sender_user_id:
            return ContactCheck.NOT_OWN
        digits = "".join(ch for ch in contact_phone if ch.isdigit())
        try:
            phone = Phone("+" + digits)
        except DomainError:
            return ContactCheck.PHONE_MISMATCH
        return ContactCheck.OK if phone == self.phone else ContactCheck.PHONE_MISMATCH

    def issue_code(
        self, code_hash: str, now: datetime, telegram_user_id: str, telegram_chat_id: str, username: str
    ) -> None:
        """Контакт сошёлся — выпускаем код. Повторный выпуск обнуляет попытки."""
        self.ensure_active(now)
        if self.telegram_user_id is not None and self.telegram_user_id != telegram_user_id:
            raise DomainError("Эту ссылку уже открыли из другого Telegram-аккаунта")
        self.telegram_user_id = telegram_user_id
        self.telegram_chat_id = telegram_chat_id
        self.telegram_username = username
        self.code_hash = code_hash
        self.code_expires_at = now + CODE_TTL
        self.code_sent_at = now
        self.attempts = 0

    def ensure_can_resend(self, now: datetime) -> None:
        self.ensure_active(now)
        if not self.contact_confirmed:
            raise DomainError("Сначала поделитесь номером в Telegram")
        if self.code_sent_at and now < self.code_sent_at + RESEND_COOLDOWN:
            left = int((self.code_sent_at + RESEND_COOLDOWN - now).total_seconds()) + 1
            raise TooManyAttemptsError(f"Новый код можно запросить через {left} с")

    def check_code(self, matches: bool, now: datetime) -> None:
        """matches — результат сверки с хешем (сверяет вызывающий: хеширование — инфраструктура)."""
        self.ensure_active(now)
        if not self.contact_confirmed:
            raise DomainError("Сначала откройте бота и поделитесь номером")
        if self.code_expires_at is None or now >= self.code_expires_at:
            raise DomainError("Код истёк — запросите новый")
        if self.attempts >= MAX_CODE_ATTEMPTS:
            raise TooManyAttemptsError("Слишком много попыток — запросите новый код")
        if not matches:
            self.attempts += 1
            left = MAX_CODE_ATTEMPTS - self.attempts
            if left <= 0:
                raise TooManyAttemptsError("Слишком много попыток — запросите новый код")
            raise DomainError(f"Неверный код. Осталось попыток: {left}")

    def complete(self, now: datetime) -> None:
        self.completed_at = now


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def mask_phone(phone: Phone) -> str:
    """+7 928 ***-**-01 — в чате бота, чтобы человек узнал свой номер, но не светить его целиком."""
    value = str(phone)
    return f"{value[:2]} {value[2:5]} ***-**-{value[-2:]}"


class ITelegramVerificationRepository(Protocol):
    """Без магазина: регистрация идёт до того, как магазин появился."""

    async def add(self, verification: TelegramVerification) -> TelegramVerification: ...
    async def save(self, verification: TelegramVerification) -> TelegramVerification: ...
    async def get_by_token(self, token: str) -> TelegramVerification | None: ...
