from dataclasses import dataclass
from enum import StrEnum

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


class ContactCheck(StrEnum):
    """Почему бот не принял контакт — у каждого случая свой текст в чате."""

    OK = "ok"
    NOT_OWN = "not_own"  # переслан чужой контакт
    PHONE_MISMATCH = "phone_mismatch"


def check_telegram_contact(
    expected: Phone, contact_phone: str, contact_user_id: str, sender_user_id: str
) -> ContactCheck:
    """Свой ли это контакт и тот ли номер, которого мы ждём.

    Единая проверка для всех сценариев подтверждения через бота: вход и
    регистрация покупателя, смена номера, регистрация и привязка владельца.
    Раньше жила в двух копиях (CustomerLoginLink и TelegramVerification), и
    в одной из них не хватало проверки на пересланный контакт.

    Два условия, и оба обязательны:
    - контакт прислан своим аккаунтом, а не переслан чужой: иначе номер
      подтверждал бы кто угодно, у кого есть контакт жертвы;
    - номер совпал с ожидаемым: номер в форме пишется руками, без сверки
      можно было бы оформить аккаунт на чужой телефон.

    Telegram отдаёт номер без «+», в международном формате.
    """
    if contact_user_id != sender_user_id:
        return ContactCheck.NOT_OWN
    digits = "".join(ch for ch in contact_phone if ch.isdigit())
    try:
        phone = Phone("+" + digits)
    except DomainError:
        return ContactCheck.PHONE_MISMATCH
    return ContactCheck.OK if phone == expected else ContactCheck.PHONE_MISMATCH
