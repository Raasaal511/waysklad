from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


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
        return f"{self.amount} ₽"
