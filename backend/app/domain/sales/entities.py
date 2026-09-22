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
    # уже полученная ранее предоплата (например, при принятии заказа с
    # витрины) — уменьшает сумму К ДОПЛАТЕ сейчас (total), но НЕ выручку:
    # товар продан по полной цене строк, просто оплата в два приёма.
    # Отдельно от discount (уступка клиенту, которая выручку уменьшает)
    prepayment: Money = field(default_factory=Money.zero)
    # сколько клиент отдал сразу при продаже «в долг» (остальное → Debt).
    # Не путать с prepayment: то — уже полученная раньше (заказ), это —
    # часть чека, оплаченная в момент продажи. Не уменьшает total/выручку.
    paid_now: Money = field(default_factory=Money.zero)
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
        """Сумма к доплате: после скидки и уже полученной предоплаты."""
        return self.subtotal - self.discount - self.prepayment

    @property
    def debt_amount(self) -> Money:
        """Остаток в долг при credit: total − paid_now. Иначе 0."""
        if self.payment_method is not PaymentMethod.CREDIT:
            return Money.zero()
        return self.total - self.paid_now

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
        if self.discount + self.prepayment > self.subtotal:
            raise DomainError("Скидка и предоплата вместе больше суммы чека")
        if self.payment_method is PaymentMethod.CREDIT and self.client_id is None:
            raise DomainError("Для продажи в долг нужно указать клиента")
        if self.paid_now > Money.zero() and self.payment_method is not PaymentMethod.CREDIT:
            raise DomainError(
                "Поле «Заплатил сейчас» доступно только при оплате «В долг»"
            )
        if self.paid_now < Money.zero():
            raise DomainError("«Заплатил сейчас» не может быть отрицательным")
        if self.payment_method is PaymentMethod.CREDIT and self.paid_now >= self.total:
            raise DomainError(
                "Клиент заплатил всю сумму — выберите „Наличные“ или „Перевод“"
            )
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
