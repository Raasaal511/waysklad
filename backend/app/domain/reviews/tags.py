from dataclasses import dataclass

# Фиксированный справочник тегов отзыва (промпт B3 п.3) — закрытый список,
# не редактируемый владельцем: чипы-фильтры на витрине должны быть предсказуемы
# и сравнимы между магазинами (как у wikkeo), а не произвольным текстом.


@dataclass(frozen=True)
class ReviewTag:
    code: str
    label: str


REVIEW_TAGS: tuple[ReviewTag, ...] = (
    ReviewTag("fast_delivery", "Быстрая доставка"),
    ReviewTag("good_packaging", "Хорошая упаковка"),
    ReviewTag("fast_reply", "Быстрый ответ"),
    ReviewTag("good_quality", "Хорошее качество"),
    ReviewTag("no_defects", "Отсутствие брака"),
    ReviewTag("as_described", "Соответствует описанию"),
    ReviewTag("good_price", "Хорошая цена"),
    ReviewTag("polite_seller", "Вежливый продавец"),
)

REVIEW_TAG_CODES: frozenset[str] = frozenset(t.code for t in REVIEW_TAGS)
_BY_CODE: dict[str, ReviewTag] = {t.code: t for t in REVIEW_TAGS}


def label_for(code: str) -> str:
    """Человекочитаемое название тега по коду — вызывающий уже проверил code
    через REVIEW_TAG_CODES (валидация при создании отзыва), здесь не ошибка,
    а невозможный случай при консистентных данных."""
    return _BY_CODE[code].label
