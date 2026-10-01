"""Регистрация владельца и привязка Telegram через бота.

Сайт → StartSignup/StartLink (ссылка на бота) → бот: DescribeVerification
(приветствие) и AcceptContact (контакт → код) → сайт: GetVerificationStatus
(опрос) и CompleteSignup/CompleteLink (код → магазин/привязка). Повторный
код — ResendCode. Тексты сообщений в чат — здесь же, чтобы бот и API писали
одинаково.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.auth.register_shop import (
    RegisterShopCommand,
    RegisterShopResult,
    create_shop,
    validate_signup,
)
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import AccessDeniedError, DomainError, NotFoundError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor
from app.domain.identity.ports import IPasswordHasher
from app.domain.identity.telegram_verification import (
    ContactCheck,
    SignupData,
    TelegramVerification,
    VerificationPurpose,
    generate_code,
    mask_phone,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def code_message(code: str) -> str:
    # <code> — в Telegram касание копирует код, не надо выделять пальцем
    return (
        f"Ваш код: <code>{code}</code>\n\n"
        "Введите его на сайте ВайСклад. Код действует 10 минут.\n"
        "Никому его не сообщайте — сотрудники ВайСклад код не спрашивают."
    )


async def _get_active(uow: IUnitOfWork, token: str) -> TelegramVerification:
    verification = await uow.telegram_verifications.get_by_token(token)
    if verification is None:
        raise NotFoundError("Ссылка не найдена — начните заново на сайте")
    return verification


# --- сайт: начало -----------------------------------------------------------


class StartSignupUseCase:
    """Форма регистрации проверена, но магазин ещё не создан — ждёт бота."""

    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, cmd: RegisterShopCommand) -> TelegramVerification:
        phone = validate_signup(cmd)
        async with self._uow as uow:
            if await uow.users.get_by_phone(str(phone)) is not None:
                raise DomainError("Этот телефон уже зарегистрирован — войдите")
            verification = TelegramVerification.start(
                VerificationPurpose.SIGNUP,
                phone,
                _now(),
                signup=SignupData(
                    shop_name=cmd.shop_name.strip(),
                    owner_name=cmd.owner_name.strip(),
                    password_hash=self._hasher.hash(cmd.password),
                    consent_at=_now(),
                ),
            )
            await uow.telegram_verifications.add(verification)
            await uow.commit()
            return verification


class StartLinkUseCase:
    """Владелец, зарегистрированный до бота, привязывает Telegram из кабинета."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> TelegramVerification:
        if actor.role is not Role.OWNER:
            raise AccessDeniedError("Подключить Telegram магазина может только владелец")
        async with self._uow as uow:
            user = await uow.users.get(actor.id)
            verification = TelegramVerification.start(
                VerificationPurpose.LINK, user.phone, _now(), user_id=user.id, tenant_id=uow.tenant_id
            )
            await uow.telegram_verifications.add(verification)
            await uow.commit()
            return verification


# --- бот ---------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationInfo:
    purpose: VerificationPurpose
    shop_name: str
    owner_name: str
    masked_phone: str


class DescribeVerificationUseCase:
    """Что показать в боте по ссылке: для кого и какой магазин."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, token: str) -> VerificationInfo:
        async with self._uow as uow:
            v = await _get_active(uow, token)
            v.ensure_active(_now())
            if v.signup is not None:
                shop_name, owner_name = v.signup.shop_name, v.signup.owner_name
            else:
                tenant = await uow.tenants.get(v.tenant_id)
                shop_name, owner_name = tenant.name, ""
            return VerificationInfo(v.purpose, shop_name, owner_name, mask_phone(v.phone))


@dataclass(frozen=True)
class ContactCommand:
    token: str
    contact_phone: str
    contact_user_id: str
    sender_user_id: str
    chat_id: str
    username: str = ""


@dataclass(frozen=True)
class ContactResult:
    check: ContactCheck
    # выдан только при ContactCheck.OK — бот отправляет его сообщением
    code: str | None = None
    masked_phone: str = ""


class AcceptContactUseCase:
    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, cmd: ContactCommand) -> ContactResult:
        async with self._uow as uow:
            v = await _get_active(uow, cmd.token)
            v.ensure_active(_now())
            check = v.check_contact(cmd.contact_phone, cmd.contact_user_id, cmd.sender_user_id)
            if check is not ContactCheck.OK:
                return ContactResult(check=check, masked_phone=mask_phone(v.phone))
            code = generate_code()
            v.issue_code(self._hasher.hash(code), _now(), cmd.sender_user_id, cmd.chat_id, cmd.username)
            await uow.telegram_verifications.save(v)
            await uow.commit()
            return ContactResult(check=check, code=code, masked_phone=mask_phone(v.phone))


# --- сайт: статус, код ------------------------------------------------------


@dataclass(frozen=True)
class VerificationStatus:
    contact_confirmed: bool
    completed: bool
    expired: bool
    expires_at: datetime
    code_sent_at: datetime | None


class GetVerificationStatusUseCase:
    """Сайт опрашивает, пока человек в Telegram: «номер подтверждён — введите код»."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, token: str) -> VerificationStatus:
        async with self._uow as uow:
            v = await _get_active(uow, token)
            return VerificationStatus(
                contact_confirmed=v.contact_confirmed,
                completed=v.completed_at is not None,
                expired=_now() >= v.expires_at,
                expires_at=v.expires_at,
                code_sent_at=v.code_sent_at,
            )


async def _check_code(uow: IUnitOfWork, hasher: IPasswordHasher, v: TelegramVerification, code: str) -> None:
    """Неверный код — попытка сохраняется до ошибки, иначе откат транзакции
    обнулил бы счётчик и код можно было бы перебирать бесконечно."""
    matches = v.code_hash is not None and hasher.verify(code.strip(), v.code_hash)
    try:
        v.check_code(matches, _now())
    except DomainError:
        await uow.telegram_verifications.save(v)
        await uow.commit()
        raise


@dataclass(frozen=True)
class SignupCompleted:
    result: RegisterShopResult
    chat_id: str
    shop_name: str


class CompleteSignupUseCase:
    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, token: str, code: str) -> SignupCompleted:
        async with self._uow as uow:
            v = await _get_active(uow, token)
            if v.purpose is not VerificationPurpose.SIGNUP or v.signup is None:
                raise DomainError("Эта ссылка не для регистрации")
            await _check_code(uow, self._hasher, v, code)
            result = await create_shop(
                uow,
                shop_name=v.signup.shop_name,
                owner_name=v.signup.owner_name,
                phone=v.phone,
                password_hash=v.signup.password_hash,
                consent_at=v.signup.consent_at,
                telegram_user_id=v.telegram_user_id,
                telegram_chat_id=v.telegram_chat_id,
            )
            v.complete(_now())
            await uow.telegram_verifications.save(v)
            await uow.commit()
            return SignupCompleted(result=result, chat_id=v.telegram_chat_id or "", shop_name=v.signup.shop_name)


@dataclass(frozen=True)
class LinkCompleted:
    chat_id: str
    shop_name: str


class CompleteLinkUseCase:
    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, actor: Actor, token: str, code: str) -> LinkCompleted:
        async with self._uow as uow:
            v = await _get_active(uow, token)
            if v.purpose is not VerificationPurpose.LINK or v.user_id != actor.id:
                raise AccessDeniedError("Эта ссылка не для вашего аккаунта")
            await _check_code(uow, self._hasher, v, code)
            user = await uow.users.get(actor.id)
            user.telegram_user_id = v.telegram_user_id
            user.telegram_verified_at = _now()
            await uow.users.save(user)
            tenant = await uow.tenants.get(uow.tenant_id)
            tenant.owner_telegram_chat_id = v.telegram_chat_id
            await uow.tenants.save(tenant)
            await uow.audit.add(AuditEntry.record(actor, "shop.connect_telegram", tenant.id, via="bot"))
            v.complete(_now())
            await uow.telegram_verifications.save(v)
            await uow.commit()
            return LinkCompleted(chat_id=v.telegram_chat_id or "", shop_name=tenant.name)


@dataclass(frozen=True)
class ResentCode:
    chat_id: str
    code: str


class ResendCodeUseCase:
    """Новый код в тот же чат — не чаще раза в минуту; отправляет вызывающий."""

    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, token: str) -> ResentCode:
        async with self._uow as uow:
            v = await _get_active(uow, token)
            v.ensure_can_resend(_now())
            code = generate_code()
            v.issue_code(
                self._hasher.hash(code), _now(), v.telegram_user_id or "", v.telegram_chat_id or "", v.telegram_username
            )
            await uow.telegram_verifications.save(v)
            await uow.commit()
            return ResentCode(chat_id=v.telegram_chat_id or "", code=code)
