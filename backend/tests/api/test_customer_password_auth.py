"""Регистрация покупателя по username + телефону + паролю и вход по паролю.

Номер подтверждается Telegram-ботом: POST /register только выпускает ссылку,
аккаунт создаёт подтверждение (ConfirmCustomerLoginLinkUseCase — тот же путь,
которым идёт обычный вход через бота).
"""

import pytest

from app.application.customers.confirm_login_link import (
    ConfirmCustomerLoginLinkCommand,
    ConfirmCustomerLoginLinkUseCase,
)
from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer

REGISTER_URL = "/api/auth/customer/register"
LOGIN_URL = "/api/auth/customer/login"


async def confirm_in_bot(make_uow, token: str, chat_id: str = "1001") -> None:
    """Подтверждение номера ботом — то, что делает handlers/start.py."""
    await ConfirmCustomerLoginLinkUseCase(make_uow()).execute(
        ConfirmCustomerLoginLinkCommand(token=token, telegram_chat_id=chat_id)
    )


async def test_register_then_confirm_then_login(client, make_uow, random_phone):
    phone = random_phone()
    response = await client.post(
        REGISTER_URL,
        json={
            "username": "vasya.01",
            "phone": phone,
            "password": "secret12345",
            "password_confirm": "secret12345",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "t.me/" in body["telegram_deep_link"]
    # токена входа ещё нет — номер не подтверждён
    assert "access_token" not in body

    # до подтверждения аккаунта не существует: войти нельзя
    denied = await client.post(
        LOGIN_URL, json={"login": "vasya.01", "password": "secret12345"}
    )
    assert denied.status_code == 400, denied.text

    await confirm_in_bot(make_uow, body["token"])

    # после подтверждения — вход по username и по телефону
    for login in ("vasya.01", phone):
        ok = await client.post(LOGIN_URL, json={"login": login, "password": "secret12345"})
        assert ok.status_code == 200, ok.text
        assert ok.json()["access_token"]
        assert ok.json()["customer"]["phone"] == phone

    # выданным токеном можно ходить в профиль
    token = ok.json()["access_token"]
    me = await client.get("/api/auth/customer/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text


async def test_login_rejects_wrong_password(client, make_uow, random_phone):
    phone = random_phone()
    response = await client.post(
        REGISTER_URL,
        json={
            "username": "petya.02",
            "phone": phone,
            "password": "secret12345",
            "password_confirm": "secret12345",
        },
    )
    await confirm_in_bot(make_uow, response.json()["token"])

    bad = await client.post(LOGIN_URL, json={"login": "petya.02", "password": "wrong-pass"})
    assert bad.status_code == 400
    # формулировка не выдаёт, существует ли логин
    assert bad.json()["detail"] == "Неверный логин или пароль"

    unknown = await client.post(
        LOGIN_URL, json={"login": "no.such.user", "password": "secret12345"}
    )
    assert unknown.status_code == 400
    assert unknown.json()["detail"] == "Неверный логин или пароль"


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"username": "ab"}, "Имя пользователя короче 3 символов"),
        ({"username": "вася-кириллица"}, "Имя пользователя: латиница, цифры, точка, дефис и подчёркивание"),
        ({"password_confirm": "other-password"}, "Пароли не совпадают"),
        ({"password": "short", "password_confirm": "short"}, "Пароль короче 8 символов"),
    ],
)
async def test_register_validation(client, random_phone, payload, expected):
    body = {
        "username": "valid.name",
        "phone": random_phone(),
        "password": "secret12345",
        "password_confirm": "secret12345",
    }
    body.update(payload)
    response = await client.post(REGISTER_URL, json=body)
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == expected


async def test_register_rejects_taken_username(client, make_uow, random_phone):
    first = await client.post(
        REGISTER_URL,
        json={
            "username": "taken.name",
            "phone": random_phone(),
            "password": "secret12345",
            "password_confirm": "secret12345",
        },
    )
    await confirm_in_bot(make_uow, first.json()["token"])

    # регистр не важен — «Taken.Name» это тот же логин
    second = await client.post(
        REGISTER_URL,
        json={
            "username": "Taken.Name",
            "phone": random_phone(),
            "password": "secret12345",
            "password_confirm": "secret12345",
        },
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "Имя пользователя занято"


async def test_register_upgrades_telegram_only_account(client, make_uow, random_phone):
    """Аккаунт, заведённый входом через Telegram, не имеет пароля — регистрация
    с тем же номером доводит его до парольного, а не создаёт второй."""
    phone = random_phone()
    async with make_uow() as uow:
        existing = await uow.customers.add(Customer(id=None, phone=Phone(phone), name="Старое имя"))
        await uow.commit()
    existing_id = existing.id

    response = await client.post(
        REGISTER_URL,
        json={
            "username": "upgraded.user",
            "phone": phone,
            "password": "secret12345",
            "password_confirm": "secret12345",
        },
    )
    assert response.status_code == 201, response.text
    await confirm_in_bot(make_uow, response.json()["token"])

    ok = await client.post(LOGIN_URL, json={"login": "upgraded.user", "password": "secret12345"})
    assert ok.status_code == 200, ok.text
    # тот же самый аккаунт, имя не затёрто
    assert ok.json()["customer"]["id"] == existing_id
    assert ok.json()["customer"]["name"] == "Старое имя"


async def test_register_rejects_phone_with_password(client, make_uow, random_phone):
    phone = random_phone()
    first = await client.post(
        REGISTER_URL,
        json={
            "username": "first.owner",
            "phone": phone,
            "password": "secret12345",
            "password_confirm": "secret12345",
        },
    )
    await confirm_in_bot(make_uow, first.json()["token"])

    second = await client.post(
        REGISTER_URL,
        json={
            "username": "second.owner",
            "phone": phone,
            "password": "secret12345",
            "password_confirm": "secret12345",
        },
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "Этот телефон уже зарегистрирован"
