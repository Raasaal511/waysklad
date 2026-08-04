from dataclasses import dataclass

import phonenumbers

from app.domain.common.exceptions import DomainError

DEFAULT_REGION = "RU"  # номера без кода страны считаем российскими (ЧР)


@dataclass(frozen=True, slots=True)
class Phone:
    """Телефон в формате E.164, например +79280001122.

    Принимает и национальный формат (89280001122, 9280001122), и международный —
    приводит к единому виду, чтобы один и тот же номер не размножался в базе
    вариантами написания.
    """

    value: str

    def __post_init__(self) -> None:
        try:
            parsed = phonenumbers.parse(self.value, DEFAULT_REGION)
        except phonenumbers.NumberParseException as exc:
            raise DomainError(f"Некорректный номер телефона: {self.value!r}") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise DomainError(f"Некорректный номер телефона: {self.value!r}")
        object.__setattr__(
            self, "value", phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        )

    def __str__(self) -> str:
        return self.value
