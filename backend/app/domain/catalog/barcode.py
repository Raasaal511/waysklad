from dataclasses import dataclass

from app.domain.common.exceptions import DomainError


@dataclass(frozen=True, slots=True)
class Barcode:
    """EAN-8/13, UPC или короткий внутренний код — только цифры."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", self.value.strip())
        if not self.value.isdigit() or not 4 <= len(self.value) <= 14:
            raise DomainError(f"Некорректный штрихкод: {self.value!r}")
