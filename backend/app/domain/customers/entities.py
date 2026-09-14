import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.common.phone import Phone

LOGIN_LINK_TTL = timedelta(minutes=10)


@dataclass
class Customer:
    """Аккаунт покупателя витрины — общий на всю платформу (не привязан к
    одному tenant), в отличие от User (сотрудник конкретного магазина). Входит
    по телефону, без пароля — подтверждение через Telegram-бота (CustomerLoginLink)."""

    id: int | None
    phone: Phone
    telegram_chat_id: str = ""
    # инкрементируется при отзыве всех токенов (logout-all) — тот же паттерн,
    # что и у User.token_version
    token_version: int = 0


@dataclass
class CustomerLoginLink:
    """Одноразовая ссылка входа: покупатель вводит телефон на витрине, получает
    deep-link на Telegram-бота — бот подтверждает владение номером, когда
    покупатель сам открывает диалог и присылает свой chat_id боту."""

    token: str
    phone: Phone
    created_at: datetime
    customer_id: int | None = None  # заполняется при подтверждении ботом
    confirmed_at: datetime | None = None

    @classmethod
    def create(cls, phone: Phone) -> "CustomerLoginLink":
        return cls(
            token=secrets.token_urlsafe(24),
            phone=phone,
            created_at=datetime.now(timezone.utc),
        )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.created_at + LOGIN_LINK_TTL

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    def confirm(self, customer_id: int) -> None:
        self.customer_id = customer_id
        self.confirmed_at = datetime.now(timezone.utc)
