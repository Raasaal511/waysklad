from aiogram.fsm.state import State, StatesGroup


class StorefrontFlow(StatesGroup):
    """Диалог покупателя: /start <slug> → каталог → карточка товара →
    количество → телефон → имя → подтверждение. Один товар = одна заявка
    (MVP) — переиспользует CreateStorefrontRequestUseCase, ту же бизнес-логику,
    что и веб-витрина."""

    browsing_catalog = State()
    viewing_product = State()
    entering_quantity = State()
    entering_phone = State()
    entering_name = State()
    confirming = State()
