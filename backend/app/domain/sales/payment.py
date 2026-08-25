from enum import StrEnum


class PaymentMethod(StrEnum):
    """Пометка, как рассчитался клиент. Реальные деньги через систему не проходят."""

    CASH = "cash"          # наличные
    TRANSFER = "transfer"  # перевод
    CREDIT = "credit"      # в долг
