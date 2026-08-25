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
