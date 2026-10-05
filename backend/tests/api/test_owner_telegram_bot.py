"""Обработчики бота для регистрации владельца — с поддельным сообщением и
настоящим FSM aiogram (в памяти): что бот отвечает на каждом шаге."""

from dataclasses import dataclass, field
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.infrastructure.config import settings
from app.infrastructure.telegram_bot.handlers.owner_verification import (
    owner_contact,
    owner_waiting_contact,
    start_owner_verification,
)
from app.infrastructure.telegram_bot.states import OwnerVerificationFlow

TG = 424242


@dataclass
class FakeUser:
    id: int = TG
    username: str = "ahmed"


@dataclass
class FakeChat:
    id: int = TG


@dataclass
class FakeContact:
    phone_number: str
    user_id: int | None = TG


@dataclass
class FakeMessage:
    contact: FakeContact | None = None
    text: str | None = None
    from_user: FakeUser = field(default_factory=FakeUser)
    chat: FakeChat = field(default_factory=FakeChat)
    answers: list[tuple[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup: Any = None, **_: Any) -> None:
        self.answers.append((text, reply_markup))


def _state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=TG, user_id=TG))


async def _start(client, phone: str) -> str:
    response = await client.post(
        "/api/auth/register",
        json={"shop_name": "Лавка", "owner_name": "Ахмед", "phone": phone, "password": "secret123", "personal_data_consent": True},
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


async def test_bot_walks_owner_to_code(client, random_phone):
    phone = random_phone()
    token = await _start(client, phone)
    state = _state()

    hello = FakeMessage()
    await start_owner_verification(hello, state, token, client.session_factory)
    text, keyboard = hello.answers[0]
    assert "Здравствуйте, Ахмед!" in text and "«Лавка»" in text
    assert phone[-2:] in text and phone[5:9] not in text  # номер замаскирован
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    assert keyboard.keyboard[0][0].request_contact is True
    assert await state.get_state() == OwnerVerificationFlow.waiting_contact.state

    # текст вместо кнопки — подсказка, состояние не теряется
    typed = FakeMessage(text=phone)
    await owner_waiting_contact(typed)
    assert "Поделиться номером" in typed.answers[0][0]

    # чужой контакт
    foreign = FakeMessage(contact=FakeContact(phone.lstrip("+"), user_id=1))
    await owner_contact(foreign, state, client.session_factory)
    assert "чужой контакт" in foreign.answers[0][0]
    assert await state.get_state() == OwnerVerificationFlow.waiting_contact.state

    # Telegram на другой номер
    wrong = FakeMessage(contact=FakeContact(random_phone().lstrip("+")))
    await owner_contact(wrong, state, client.session_factory)
    assert "не совпадает" in wrong.answers[0][0]

    # свой номер — клавиатура убрана, код пришёл, состояние сброшено
    ok = FakeMessage(contact=FakeContact(phone.lstrip("+")))
    await owner_contact(ok, state, client.session_factory)
    assert "подтверждён" in ok.answers[0][0]
    assert isinstance(ok.answers[0][1], ReplyKeyboardRemove)
    code_text = ok.answers[1][0]
    code = code_text.split("<code>")[1].split("</code>")[0]
    assert len(code) == 6 and code.isdigit()
    assert await state.get_state() is None

    done = await client.post("/api/auth/register/confirm", json={"token": token, "code": code})
    assert done.status_code == 201, done.text


async def test_bot_rejects_unknown_link(client):
    message = FakeMessage()
    await start_owner_verification(message, _state(), "no-such-token-123", client.session_factory)
    assert "не найдена" in message.answers[0][0]
    assert isinstance(message.answers[0][1], ReplyKeyboardRemove)


async def test_back_to_site_returns_to_signup_code(client, random_phone, monkeypatch):
    """«Вернуться на сайт» открывается в новой вкладке — без токена там был бы вход."""
    monkeypatch.setattr(settings, "public_base_url", "https://shop.example")
    phone = random_phone()
    token = await _start(client, phone)
    state = _state()
    await start_owner_verification(FakeMessage(), state, token, client.session_factory)

    ok = FakeMessage(contact=FakeContact(phone.lstrip("+")))
    await owner_contact(ok, state, client.session_factory)
    button = ok.answers[1][1].inline_keyboard[0][0]
    assert button.url == f"https://shop.example/login?signup={token}"
