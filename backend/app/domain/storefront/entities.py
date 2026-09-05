from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.domain.common.exceptions import DomainError


class StorefrontRequestStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"  # конвертирована в Order — see Order.id
    REJECTED = "rejected"


@dataclass
class StorefrontRequestLine:
    product_id: int
    quantity: Decimal
    variant_id: int | None = None


@dataclass
class StorefrontRequest:
    """Сырая заявка с публичной витрины — лёгкая сущность без склада/даты/резерва
    остатка. Становится полноценным Order только когда владелец её примет
    (ChangeStorefrontRequestStatus) и сам укажет склад/дату готовности."""

    id: int | None
    customer_name: str
    lines: list[StorefrontRequestLine] = field(default_factory=list)
    customer_phone: str = ""
    # заполнено, только если заявка создана из Telegram-бота витрины — задел
    # на будущее (push покупателю ответа владельца в чат), не используется
    # веб-витриной (там доступ по access_token)
    customer_telegram_chat_id: str = ""
    note: str = ""
    status: StorefrontRequestStatus = StorefrontRequestStatus.NEW
    order_id: int | None = None  # заполняется при принятии
    # непредсказуемый токен для доступа покупателя к чату своей заявки без
    # аккаунта — выдаётся один раз в ответе на создание, дальше хранится
    # на стороне покупателя (localStorage); заполняется репозиторием при add()
    access_token: str = ""
    created_at: datetime | None = None
    # заполняется только get_by_token() — единственный способ анонимного
    # покупателя узнать tenant своей заявки, чтобы открыть tenant-scoped UoW;
    # аналог User.tenant_id (тот же паттерн: контекст, знающий о tenant извне)
    tenant_id: int | None = None

    def validate(self) -> None:
        if not self.customer_name.strip():
            raise DomainError("Укажите имя")
        if not self.lines:
            raise DomainError("Заявка без товаров")

    def accept(self, order_id: int) -> None:
        if self.status != StorefrontRequestStatus.NEW:
            raise DomainError("Заявка уже обработана")
        self.status = StorefrontRequestStatus.ACCEPTED
        self.order_id = order_id

    def reject(self) -> None:
        if self.status != StorefrontRequestStatus.NEW:
            raise DomainError("Заявка уже обработана")
        self.status = StorefrontRequestStatus.REJECTED


class MessageAuthor(StrEnum):
    CUSTOMER = "customer"
    STAFF = "staff"


@dataclass
class StorefrontMessage:
    """Сообщение в чате заявки — живёт вместе с StorefrontRequest, не
    отдельная самостоятельная сущность (переживает и принятие заявки)."""

    id: int | None
    request_id: int
    author: MessageAuthor
    text: str
    created_at: datetime | None = None

    def validate(self) -> None:
        if not self.text.strip():
            raise DomainError("Пустое сообщение")
