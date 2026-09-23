from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")
_NARROW_NBSP = "\u202f"  # как formatMoney на фронте


def format_rub(value: Money | Decimal | int | str) -> str:
    """Сумма для людей: «63 200 ₽», «1 250,50 ₽», «0 ₽». Без лишних ,00 у целых."""
    if isinstance(value, Money):
        amount = value.amount
    else:
        amount = Decimal(str(value)).quantize(_CENT, ROUND_HALF_UP)

    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    whole = int(amount)
    cents = int((amount - whole) * 100)

    whole_str = f"{whole:,}".replace(",", _NARROW_NBSP)
    if cents == 0:
        body = whole_str
    else:
        body = f"{whole_str},{cents:02d}"
    return f"{sign}{body} ₽"


@dataclass(frozen=True, order=True, slots=True)
class Money:
    """Денежная сумма в рублях. Только Decimal — никаких float."""

    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "amount", Decimal(str(self.amount)).quantize(_CENT, ROUND_HALF_UP)
        )

    @classmethod
    def of(cls, value: int | str | Decimal) -> Money:
        return cls(Decimal(str(value)))

    @classmethod
    def zero(cls) -> Money:
        return cls(Decimal("0"))

    def __add__(self, other: Money) -> Money:
        return Money(self.amount + other.amount)

    def __sub__(self, other: Money) -> Money:
        return Money(self.amount - other.amount)

    def __mul__(self, factor: Decimal | int) -> Money:
        return Money(self.amount * Decimal(str(factor)))

    def is_negative(self) -> bool:
        return self.amount < 0

    def __str__(self) -> str:
        return format_rub(self)

