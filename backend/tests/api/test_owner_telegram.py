from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.application.auth.register_shop import RegisterShopCommand, RegisterShopUseCase
from app.application.auth.telegram_signup import (
    AcceptContactUseCase,
    ContactCommand,
    ResendCodeUseCase,
)
from app.domain.identity.telegram_verification import ContactCheck
from app.infrastructure.config import settings
from app.infrastructure.db.models.identity import TelegramVerificationModel
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.security import BcryptPasswordHasher
from tests.conftest import register_via_bot

TG = "555000111"


def _form(phone: str, **extra) -> dict:
    return {
        "shop_name": "Лавка у дома",
        "owner_name": "Ахмед",
        "phone": phone,
        "password": "secret123",
        "personal_data_consent": True,
        **extra,
    }


async def _contact(client, token: str, phone: str, *, sender: str = TG, owner: str | None = None):
    """То, что делает бот, когда человек нажал «Поделиться номером»."""
    return await AcceptContactUseCase(
        SqlAlchemyUnitOfWork(None, session_factory=client.session_factory), BcryptPasswordHasher()
    ).execute(
        ContactCommand(
            token=token,
            contact_phone=phone.lstrip("+"),
            contact_user_id=owner or sender,
            sender_user_id=sender,
            chat_id=sender,
        )
    )


async def _status(client, token: str) -> dict:
    response = await client.get(f"/api/auth/telegram/verification?token={token}")
    assert response.status_code == 200, response.text
    return response.json()


async def _shift(client, token: str, **values) -> None:
    """Сдвинуть время в прошлое — проверить истечение без sleep."""
    async with client.session_factory() as session:
        await session.execute(
            update(TelegramVerificationModel).where(TelegramVerificationModel.token == token).values(**values)
        )
        await session.commit()


async def test_signup_full_flow(client, random_phone):
    phone = random_phone()
    start = await client.post("/api/auth/register", json=_form(phone))
    assert start.status_code == 201, start.text
    body = start.json()
    token = body["token"]
    assert body["telegram_link"] == f"https://t.me/{settings.telegram_bot_username_clean}?start=reg_{token}"

    # магазина ещё нет: войти нельзя, пока номер не подтверждён
    login = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123"})
    assert login.status_code in (401, 403)
    assert (await _status(client, token))["contact_confirmed"] is False

    result = await _contact(client, token, phone)
    assert result.check is ContactCheck.OK and result.code is not None
    assert (await _status(client, token))["contact_confirmed"] is True

    wrong = await client.post("/api/auth/register/confirm", json={"token": token, "code": "000000" if result.code != "000000" else "111111"})
    assert wrong.status_code == 400
    assert "Осталось попыток: 4" in wrong.json()["detail"]

    done = await client.post("/api/auth/register/confirm", json={"token": token, "code": result.code})
    assert done.status_code == 201, done.text
    assert done.json()["user"]["role"] == "owner"
    assert done.json()["user"]["telegram_verified"] is True
    headers = {"Authorization": f"Bearer {done.json()['access_token']}"}

    # Telegram владельца сразу стал каналом сводок и уведомлений
    shop = (await client.get("/api/auth/shop", headers=headers)).json()
    assert shop["owner_telegram_chat_id"] == TG
    assert (await _status(client, token))["completed"] is True

    # ссылка одноразовая
    again = await client.post("/api/auth/register/confirm", json={"token": token, "code": result.code})
    assert again.status_code == 400


async def test_contact_must_be_own_and_match_phone(client, random_phone):
    phone = random_phone()
    token = (await client.post("/api/auth/register", json=_form(phone))).json()["token"]

    # переслали чужой контакт
    assert (await _contact(client, token, phone, owner="999")).check is ContactCheck.NOT_OWN
    # Telegram на другой номер
    other = await _contact(client, token, random_phone())
    assert other.check is ContactCheck.PHONE_MISMATCH and other.code is None
    assert other.masked_phone.endswith(phone[-2:])
    assert (await _status(client, token))["contact_confirmed"] is False


async def test_phone_already_registered_is_rejected_before_bot(client, random_phone):
    phone = random_phone()
    assert (await register_via_bot(client, _form(phone))).status_code == 201
    response = await client.post("/api/auth/register", json=_form(phone))
    assert response.status_code == 400
    assert "уже зарегистрирован" in response.json()["detail"]


async def test_form_validation_before_bot(client, random_phone):
    no_consent = await client.post("/api/auth/register", json=_form(random_phone(), personal_data_consent=False))
    assert no_consent.status_code == 400
    blank_shop = await client.post("/api/auth/register", json=_form(random_phone(), shop_name="   "))
    assert blank_shop.status_code == 400


async def test_expired_link(client, random_phone):
    phone = random_phone()
    token = (await client.post("/api/auth/register", json=_form(phone))).json()["token"]
    await _shift(client, token, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    with pytest.raises(Exception, match="устарела"):
        await _contact(client, token, phone)
    assert (await _status(client, token))["expired"] is True


async def test_code_attempts_are_limited_and_persisted(client, random_phone):
    """Неверная попытка сохраняется даже при ошибке — иначе откат транзакции
    обнулял бы счётчик и код можно было бы перебирать."""
    phone = random_phone()
    token = (await client.post("/api/auth/register", json=_form(phone))).json()["token"]
    code = (await _contact(client, token, phone)).code
    wrong = "000000" if code != "000000" else "111111"
    statuses = [
        (await client.post("/api/auth/register/confirm", json={"token": token, "code": wrong})).status_code
        for _ in range(5)
    ]
    assert statuses == [400, 400, 400, 400, 429]
    # даже верный код уже не принимается — нужен новый
    final = await client.post("/api/auth/register/confirm", json={"token": token, "code": code})
    assert final.status_code == 429


async def test_resend_code(client, random_phone):
    phone = random_phone()
    token = (await client.post("/api/auth/register", json=_form(phone))).json()["token"]

    # до контакта слать некуда
    early = await client.post("/api/auth/telegram/verification/resend", json={"token": token})
    assert early.status_code == 400

    first = (await _contact(client, token, phone)).code
    too_soon = await client.post("/api/auth/telegram/verification/resend", json={"token": token})
    assert too_soon.status_code == 429

    await _shift(client, token, code_sent_at=datetime.now(timezone.utc) - timedelta(minutes=2))
    sent = await ResendCodeUseCase(
        SqlAlchemyUnitOfWork(None, session_factory=client.session_factory), BcryptPasswordHasher()
    ).execute(token)
    assert sent.chat_id == TG
    if sent.code != first:
        stale = await client.post("/api/auth/register/confirm", json={"token": token, "code": first})
        assert stale.status_code == 400
    done = await client.post("/api/auth/register/confirm", json={"token": token, "code": sent.code})
    assert done.status_code == 201, done.text


async def test_registration_unavailable_without_bot(client, random_phone, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_username", "")
    response = await client.post("/api/auth/register", json=_form(random_phone()))
    assert response.status_code == 503


async def _legacy_owner(client, make_uow, random_phone) -> tuple[dict, str]:
    """Владелец, зарегистрированный до бота: Telegram не привязан."""
    phone = random_phone()
    await RegisterShopUseCase(make_uow(None), BcryptPasswordHasher()).execute(
        RegisterShopCommand("Старая лавка", "Магомед", phone, "secret123", True)
    )
    login = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123"})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["telegram_verified"] is False
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, phone


async def test_existing_owner_links_telegram(client, make_uow, random_phone):
    headers, phone = await _legacy_owner(client, make_uow, random_phone)
    assert (await client.get("/api/auth/shop", headers=headers)).json()["owner_telegram_chat_id"] is None

    start = await client.post("/api/auth/telegram/link", headers=headers)
    assert start.status_code == 201, start.text
    token = start.json()["token"]
    assert "?start=link_" in start.json()["telegram_link"]

    code = (await _contact(client, token, phone)).code
    done = await client.post("/api/auth/telegram/link/confirm", headers=headers, json={"token": token, "code": code})
    assert done.status_code == 200, done.text
    assert done.json()["owner_telegram_chat_id"] == TG
    relogin = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123"})
    assert relogin.json()["user"]["telegram_verified"] is True


async def test_link_is_owner_only_and_not_transferable(client, make_uow, random_phone, owner_headers):
    seller_phone = random_phone()
    await client.post(
        "/api/auth/employees", headers=owner_headers,
        json={"name": "Продавец", "phone": seller_phone, "password": "secret123", "role": "seller"},
    )
    seller = await client.post("/api/auth/login", json={"phone": seller_phone, "password": "secret123"})
    seller_headers = {"Authorization": f"Bearer {seller.json()['access_token']}"}
    assert (await client.post("/api/auth/telegram/link", headers=seller_headers)).status_code == 403

    # чужая ссылка привязки не подтверждается из другого аккаунта
    headers, phone = await _legacy_owner(client, make_uow, random_phone)
    token = (await client.post("/api/auth/telegram/link", headers=headers)).json()["token"]
    code = (await _contact(client, token, phone)).code
    stolen = await client.post(
        "/api/auth/telegram/link/confirm", headers=owner_headers, json={"token": token, "code": code}
    )
    assert stolen.status_code == 403


async def test_employee_limit_is_ten(client, owner_headers, random_phone):
    async def add(phone: str):
        return await client.post(
            "/api/auth/employees", headers=owner_headers,
            json={"name": "Сотрудник", "phone": phone, "password": "secret123", "role": "seller"},
        )

    created = []
    for _ in range(10):
        response = await add(random_phone())
        assert response.status_code == 201, response.text
        created.append(response.json())

    eleventh = await add(random_phone())
    assert eleventh.status_code == 400
    assert "10 сотрудников" in eleventh.json()["detail"]

    # отключённый не занимает место — но включить его обратно сверх лимита нельзя
    first = created[0]
    off = await client.patch(
        f"/api/auth/employees/{first['id']}", headers=owner_headers,
        json={"name": first["name"], "role": "seller", "is_active": False},
    )
    assert off.status_code == 200, off.text
    assert (await add(random_phone())).status_code == 201
    back = await client.patch(
        f"/api/auth/employees/{first['id']}", headers=owner_headers,
        json={"name": first["name"], "role": "seller", "is_active": True},
    )
    assert back.status_code == 400


async def test_owner_resets_employee_password(client, owner_headers, random_phone):
    phone = random_phone()
    employee = (
        await client.post(
            "/api/auth/employees", headers=owner_headers,
            json={"name": "Зара", "phone": phone, "password": "old-pass1", "role": "seller"},
        )
    ).json()
    old_session = await client.post("/api/auth/login", json={"phone": phone, "password": "old-pass1"})
    old_headers = {"Authorization": f"Bearer {old_session.json()['access_token']}"}

    response = await client.patch(
        f"/api/auth/employees/{employee['id']}", headers=owner_headers,
        json={"name": "Зара", "role": "seller", "is_active": True, "password": "new-pass2"},
    )
    assert response.status_code == 200, response.text

    assert (await client.post("/api/auth/login", json={"phone": phone, "password": "old-pass1"})).status_code in (401, 403)
    assert (await client.post("/api/auth/login", json={"phone": phone, "password": "new-pass2"})).status_code == 200
    # старая сессия сотрудника закрыта
    assert (await client.get("/api/notifications", headers=old_headers)).status_code == 401
