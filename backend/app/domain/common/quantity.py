from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.common.exceptions import DomainError


@dataclass(frozen=True, slots=True)
class Unit:
    code: str
    name: str
    fractional: bool = False


# Предустановленные единицы (README п. 6.1); свои единицы tenant добавляет в справочник.
UNITS: dict[str, Unit] = {
    u.code: u
    for u in (
        Unit("pcs", "шт"),
        Unit("kg", "кг", fractional=True),
        Unit("g", "г", fractional=True),
        Unit("l", "л", fractional=True),
        Unit("ml", "мл", fractional=True),
        Unit("m", "м", fractional=True),
        Unit("m2", "м²", fractional=True),
        Unit("m3", "м³", fractional=True),
        Unit("pack", "упаковка"),
        Unit("bag", "мешок"),
        Unit("roll", "рулон"),
    )
}


@dataclass(frozen=True, slots=True)
class Quantity:
    value: Decimal
    unit: Unit

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", Decimal(str(self.value)))
        if self.value < 0:
            raise DomainError("Количество не может быть отрицательным")
        if not self.unit.fractional and self.value != self.value.to_integral_value():
            raise DomainError(f"Единица «{self.unit.name}» не допускает дробное количество")

    def __add__(self, other: Quantity) -> Quantity:
        self._same_unit(other)
        return Quantity(self.value + other.value, self.unit)

    def __sub__(self, other: Quantity) -> Quantity:
        self._same_unit(other)
        return Quantity(self.value - other.value, self.unit)

    def _same_unit(self, other: Quantity) -> None:
        if self.unit != other.unit:
            raise DomainError(f"Нельзя смешивать {self.unit.name} и {other.unit.name}")

    @property
    def formatted(self) -> str:
        """Строка для отображения: "1" для шт, "1.5" для кг — без хвостовых нулей Decimal(14,3)."""
        normalized = self.value.normalize()
        # normalize() может вернуть экспоненциальную форму (напр. 1E+2) — приводим обратно
        return format(normalized, "f") if "E" in str(normalized) else str(normalized)
