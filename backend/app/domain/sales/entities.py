from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.common.exceptions import DomainError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity
from app.domain.sales.payment import PaymentMethod


@dataclass
class SaleLine:
    product_id: int
    quantity: Quantity
    price: Money  # цена на момент продажи
    purchase_price: Money = field(default_factory=Money.zero)  # закупочная на момент продажи — для прибыли
    variant_id: int | None = None
    id: int | None = None

    @property
    def total(self) -> Money:
        return self.price * self.quantity.value

    @property
    def profit(self) -> Money:
        return (self.price - self.purchase_price) * self.quantity.value


@dataclass
class Sale:
    id: int | None
    warehouse_id: int
    seller_id: int
    payment_method: PaymentMethod
    lines: list[SaleLine] = field(default_factory=list)
    discount: Money = field(default_factory=Money.zero)
    client_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    client_op_id: str | None = None  # id операции с устройства — идемпотентность офлайн-очереди
    note: str = ""
    deleted_at: datetime | None = None
    cash_received: Money | None = None  # сколько внёс клиент наличными (снимок на момент продажи)
    order_id: int | None = None  # заполнен, если продажа — результат выдачи заказа
    # клиент не забрал сдачу (округление в пользу магазина) — реальная
    # доплата сверх цены товара, поэтому не смешивается со скидкой/ценой строк,
    # учитывается отдельной строкой в аналитике (не искажает revenue по товару)
    change_kept: Money = field(default_factory=Money.zero)

    @property
    def subtotal(self) -> Money:
        total = Money.zero()
        for line in self.lines:
            total = total + line.total
        return total

    @property
    def total(self) -> Money:
        """Сумма чека после скидки."""
        return self.subtotal - self.discount

    def change_for(self, cash_received: Money) -> Money:
        """Сдача, реально выдаваемая на руки — за вычетом change_kept
        (клиент добровольно не забрал часть/всю сдачу)."""
        if cash_received < self.total:
            raise DomainError("Получено меньше суммы чека")
        return cash_received - self.total - self.change_kept

    def validate(self) -> None:
        if not self.lines:
            raise DomainError("Продажа без позиций")
        if self.discount > self.subtotal:
            raise DomainError("Скидка больше суммы чека")
        if self.payment_method is PaymentMethod.CREDIT and self.client_id is None:
            raise DomainError("Для продажи в долг нужно указать клиента")
        if self.change_kept > Money.zero():
            if self.cash_received is None:
                raise DomainError("«Сдача не взята» указывается только вместе с суммой наличных")
            if self.change_kept > self.cash_received - self.total:
                raise DomainError("«Сдача не взята» не может быть больше самой сдачи")


@dataclass
class SaleReturnLine:
    sale_line_id: int
    quantity: Quantity
    id: int | None = None


@dataclass
class SaleReturn:
    """Возврат товара по продаже: остаток возвращается на склад, долг (если был) уменьшается."""

    id: int | None
    sale_id: int
    author_id: int
    lines: list[SaleReturnLine] = field(default_factory=list)
    note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    client_op_id: str | None = None  # id операции с устройства — идемпотентность офлайн-очереди

    def validate(self) -> None:
        if not self.lines:
            raise DomainError("Возврат без позиций")
