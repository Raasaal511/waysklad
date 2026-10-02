from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common.phone import Phone
from app.domain.identity.telegram_verification import (
    ITelegramVerificationRepository,
    SignupData,
    TelegramVerification,
    VerificationPurpose,
)
from app.infrastructure.db.models.identity import TelegramVerificationModel


def _to_entity(m: TelegramVerificationModel) -> TelegramVerification:
    signup = None
    if m.shop_name is not None and m.password_hash is not None and m.consent_at is not None:
        signup = SignupData(
            shop_name=m.shop_name,
            owner_name=m.owner_name or "",
            password_hash=m.password_hash,
            consent_at=m.consent_at,
        )
    return TelegramVerification(
        id=m.id,
        token=m.token,
        purpose=VerificationPurpose(m.purpose),
        phone=Phone(m.phone),
        expires_at=m.expires_at,
        created_at=m.created_at,
        signup=signup,
        user_id=m.user_id,
        tenant_id=m.tenant_id,
        telegram_user_id=m.telegram_user_id,
        telegram_chat_id=m.telegram_chat_id,
        telegram_username=m.telegram_username,
        code_hash=m.code_hash,
        code_expires_at=m.code_expires_at,
        code_sent_at=m.code_sent_at,
        attempts=m.attempts,
        code_issues=m.code_issues,
        completed_at=m.completed_at,
    )


def _apply(m: TelegramVerificationModel, v: TelegramVerification) -> None:
    m.token = v.token
    m.purpose = v.purpose.value
    m.phone = str(v.phone)
    if v.signup is not None:
        m.shop_name = v.signup.shop_name
        m.owner_name = v.signup.owner_name
        m.password_hash = v.signup.password_hash
        m.consent_at = v.signup.consent_at
    m.user_id = v.user_id
    m.tenant_id = v.tenant_id
    m.telegram_user_id = v.telegram_user_id
    m.telegram_chat_id = v.telegram_chat_id
    m.telegram_username = v.telegram_username
    m.code_hash = v.code_hash
    m.code_expires_at = v.code_expires_at
    m.code_sent_at = v.code_sent_at
    m.attempts = v.attempts
    m.code_issues = v.code_issues
    m.expires_at = v.expires_at
    m.created_at = v.created_at
    m.completed_at = v.completed_at


class SqlAlchemyTelegramVerificationRepository(ITelegramVerificationRepository):
    """Сессия напрямую, без магазина — как у feedback/platform."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, verification: TelegramVerification) -> TelegramVerification:
        model = TelegramVerificationModel()
        _apply(model, verification)
        self._session.add(model)
        await self._session.flush()
        verification.id = model.id
        return verification

    async def save(self, verification: TelegramVerification) -> TelegramVerification:
        model = await self._session.get(TelegramVerificationModel, verification.id)
        _apply(model, verification)
        await self._session.flush()
        return verification

    async def get_by_token(self, token: str) -> TelegramVerification | None:
        model = (
            await self._session.execute(
                select(TelegramVerificationModel).where(TelegramVerificationModel.token == token)
            )
        ).scalar_one_or_none()
        return _to_entity(model) if model else None
