from decimal import Decimal

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.domain.catalog.entities import Product

_PAGE_SIZE = 8


def catalog_keyboard(products: list[Product], offset: int, total: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=p.name[:60], callback_data=f"product:{p.id}")]
        for p in products
    ]
    nav: list[InlineKeyboardButton] = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"page:{max(0, offset - _PAGE_SIZE)}"))
    if offset + _PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"page:{offset + _PAGE_SIZE}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Заказать", callback_data=f"order:{product_id}")],
            [InlineKeyboardButton(text="◀ К каталогу", callback_data="page:0")],
        ]
    )


def quantity_keyboard(quantity: Decimal, step: Decimal) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="−", callback_data="qty:dec"),
                InlineKeyboardButton(text=str(quantity), callback_data="qty:noop"),
                InlineKeyboardButton(text="+", callback_data="qty:inc"),
            ],
            [InlineKeyboardButton(text="Далее ▶", callback_data="qty:confirm")],
        ]
    )


def phone_request_keyboard() -> ReplyKeyboardMarkup:
    # ReplyKeyboardButton с request_contact — единственный способ получить
    # реальный номер без ручного ввода; текстом покупатель может написать
    # "пропустить", это ловится хендлером отдельно (см. handlers/checkout.py)
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поделиться номером телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def owner_contact_keyboard() -> ReplyKeyboardMarkup:
    # не one_time: если номер не совпал, кнопка нужна снова, а не прятать её
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        input_field_placeholder="Нажмите «Поделиться номером»",
    )


def back_to_site_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Вернуться на сайт", url=url)]])


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить заявку", callback_data="confirm:yes")],
            [InlineKeyboardButton(text="Отмена", callback_data="confirm:cancel")],
        ]
    )
