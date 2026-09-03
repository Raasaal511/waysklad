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
    note: str = ""
    status: StorefrontRequestStatus = StorefrontRequestStatus.NEW
    order_id: int | None = None  # заполняется при принятии
    created_at: datetime | None = None

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
