import re

from dataclasses import dataclass

from app.domain.common.exceptions import DomainError

_PATTERN = re.compile(r"^[A-Z0-9\-]{4,32}$")


@dataclass(frozen=True, slots=True)
class Barcode:
    """EAN-8/13, UPC (только цифры) либо Code128/Code39 (буквы, цифры, дефис)."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", self.value.strip().upper())
        if not _PATTERN.match(self.value):
            raise DomainError(f"Некорректный штрихкод: {self.value!r}")
