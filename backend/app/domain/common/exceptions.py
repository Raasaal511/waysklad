class DomainError(Exception):
    """Нарушение бизнес-правила."""


class NotFoundError(DomainError):
    """Объект не найден (или принадлежит другому магазину)."""


class AccessDeniedError(DomainError):
    """Действие недоступно для роли (продавец не видит закупочные цены)."""


class InsufficientStockError(DomainError):
    """Недостаточно остатка на складе."""


class OverRepaymentError(DomainError):
    """Погашение больше остатка долга."""


class InvalidFilterError(DomainError):
    """Недопустимое поле, оператор или сортировка в query-параметрах списка."""


class ClientHasDebtError(DomainError):
    """Попытка деактивировать клиента с непогашенным долгом без force=True."""


class TooManyAttemptsError(DomainError):
    """Исчерпан лимит попыток или частоты — отдаётся как 429, а не 400:
    клиенту важно отличать «неверные данные» от «подождите»."""

    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after
