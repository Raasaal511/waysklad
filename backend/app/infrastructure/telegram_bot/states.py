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


class CustomerLoginFlow(StatesGroup):
    """Вход и регистрация покупателя: /start login_<token> → ждём контакт
    кнопкой. Номер в форме пишется руками, поэтому подтверждает его только
    контакт самого Telegram."""

    waiting_contact = State()


class CustomerPhoneChangeFlow(StatesGroup):
    """Смена номера: /start chphone_<token> → ждём контакт кнопкой.
    Отдельно от CustomerLoginFlow — там вход, здесь смена у вошедшего, и
    сверяется контакт с новым номером, а не с номером аккаунта."""

    waiting_contact = State()


class OwnerVerificationFlow(StatesGroup):
    """Регистрация владельца / привязка Telegram: /start reg_<token> или
    link_<token> → ждём контакт кнопкой → код для сайта. Токен — в данных
    состояния, чтобы контакт относился к той ссылке, по которой пришли."""

    waiting_contact = State()
