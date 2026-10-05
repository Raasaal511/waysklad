"""Смена номера вошедшим покупателем: сайт выдаёт ссылку, подтверждает
контакт в Telegram — владелец НОВОГО номера.

Подтверждение дёргается через use case: именно так его вызывает бот, а
поднимать настоящий Telegram в тестах нечем.
"""

import pytest

from app.application.customers.change_phone import (
    ConfirmCustomerPhoneChangeCommand,
    ConfirmCustomerPhoneChangeUseCase,
)
from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer


def _contact(phone: str, user_id: str = "777") -> dict:
    """Контакт, который Telegram прислал бы при нажатии «Поделиться номером»:
    телефон без «+», и отправитель == владелец контакта."""
    return {
        "telegram_chat_id": "42",
        "contact_phone": phone.lstrip("+"),
        "contact_user_id": user_id,
        "sender_user_id": user_id,
    }


async def test_phone_change_requires_auth(client):
    response = await client.post(
        "/api/auth/customer/me/phone-change", json={"new_phone": "+79280000001"}
    )
    assert response.status_code == 401, response.text


async def test_phone_change_full_flow(client, customer_headers, make_uow, random_phone):
    headers, old_phone = await customer_headers()
    new_phone = random_phone()

    response = await client.post(
        "/api/auth/customer/me/phone-change", headers=headers, json={"new_phone": new_phone}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token"]
    assert f"start=chphone_{body['token']}" in body["telegram_deep_link"]

    # до подтверждения номер прежний
    profile = await client.get("/api/auth/customer/me", headers=headers)
    assert profile.json()["phone"] == old_phone

    async with make_uow() as uow:
        await ConfirmCustomerPhoneChangeUseCase(uow).execute(
            ConfirmCustomerPhoneChangeCommand(token=body["token"], **_contact(new_phone))
        )

    profile = await client.get("/api/auth/customer/me", headers=headers)
    assert profile.json()["phone"] == new_phone
    assert profile.json()["phone_verified"] is True


async def test_phone_change_rejects_contact_of_old_number(
    client, customer_headers, make_uow, random_phone
):
    """Подтверждает владелец нового номера. Иначе, имея доступ только к
    старому телефону, можно было бы перевести аккаунт на чужой."""
    headers, old_phone = await customer_headers()
    new_phone = random_phone()

    response = await client.post(
        "/api/auth/customer/me/phone-change", headers=headers, json={"new_phone": new_phone}
    )
    token = response.json()["token"]

    async with make_uow() as uow:
        with pytest.raises(DomainError):
            await ConfirmCustomerPhoneChangeUseCase(uow).execute(
                ConfirmCustomerPhoneChangeCommand(token=token, **_contact(old_phone))
            )

    profile = await client.get("/api/auth/customer/me", headers=headers)
    assert profile.json()["phone"] == old_phone


async def test_phone_change_rejects_forwarded_contact(
    client, customer_headers, make_uow, random_phone
):
    """Переслать чужой контакт нельзя: отправитель должен быть его владельцем."""
    headers, old_phone = await customer_headers()
    new_phone = random_phone()

    response = await client.post(
        "/api/auth/customer/me/phone-change", headers=headers, json={"new_phone": new_phone}
    )
    token = response.json()["token"]

    forwarded = _contact(new_phone)
    forwarded["sender_user_id"] = "999"  # переслал кто-то другой

    async with make_uow() as uow:
        with pytest.raises(DomainError):
            await ConfirmCustomerPhoneChangeUseCase(uow).execute(
                ConfirmCustomerPhoneChangeCommand(token=token, **forwarded)
            )

    profile = await client.get("/api/auth/customer/me", headers=headers)
    assert profile.json()["phone"] == old_phone


async def test_phone_change_rejects_number_of_another_account(
    client, customer_headers, make_uow, random_phone
):
    headers, old_phone = await customer_headers()
    taken_phone = random_phone()
    async with make_uow() as uow:
        await uow.customers.add(Customer(id=None, phone=Phone(taken_phone)))
        await uow.commit()

    response = await client.post(
        "/api/auth/customer/me/phone-change", headers=headers, json={"new_phone": taken_phone}
    )
    assert response.status_code == 400, response.text
    assert "уже зарегистрирован" in response.text

    profile = await client.get("/api/auth/customer/me", headers=headers)
    assert profile.json()["phone"] == old_phone


async def test_phone_change_rejects_current_number_when_verified(
    client, customer_headers, make_uow, random_phone
):
    headers, old_phone = await customer_headers()
    new_phone = random_phone()
    # подтверждаем номер, чтобы повторное подтверждение стало бессмысленным
    response = await client.post(
        "/api/auth/customer/me/phone-change", headers=headers, json={"new_phone": new_phone}
    )
    async with make_uow() as uow:
        await ConfirmCustomerPhoneChangeUseCase(uow).execute(
            ConfirmCustomerPhoneChangeCommand(
                token=response.json()["token"], **_contact(new_phone)
            )
        )

    response = await client.post(
        "/api/auth/customer/me/phone-change", headers=headers, json={"new_phone": new_phone}
    )
    assert response.status_code == 400, response.text
    assert "уже подтверждён" in response.text


async def test_unverified_customer_can_confirm_own_number(
    client, customer_headers, make_uow
):
    """Старый аккаунт с phone_verified=false подтверждает свой же номер —
    это то, куда ведёт баннер в профиле."""
    headers, phone = await customer_headers()
    assert (await client.get("/api/auth/customer/me", headers=headers)).json()[
        "phone_verified"
    ] is False

    response = await client.post(
        "/api/auth/customer/me/phone-change", headers=headers, json={"new_phone": phone}
    )
    assert response.status_code == 200, response.text

    async with make_uow() as uow:
        await ConfirmCustomerPhoneChangeUseCase(uow).execute(
            ConfirmCustomerPhoneChangeCommand(token=response.json()["token"], **_contact(phone))
        )

    profile = (await client.get("/api/auth/customer/me", headers=headers)).json()
    assert profile["phone"] == phone
    assert profile["phone_verified"] is True


async def test_phone_change_token_is_single_use(
    client, customer_headers, make_uow, random_phone
):
    headers, _ = await customer_headers()
    new_phone = random_phone()

    response = await client.post(
        "/api/auth/customer/me/phone-change", headers=headers, json={"new_phone": new_phone}
    )
    token = response.json()["token"]

    async with make_uow() as uow:
        await ConfirmCustomerPhoneChangeUseCase(uow).execute(
            ConfirmCustomerPhoneChangeCommand(token=token, **_contact(new_phone))
        )

    async with make_uow() as uow:
        with pytest.raises(DomainError):
            await ConfirmCustomerPhoneChangeUseCase(uow).execute(
                ConfirmCustomerPhoneChangeCommand(token=token, **_contact(new_phone))
            )


async def test_phone_change_unknown_token(make_uow):
    async with make_uow() as uow:
        with pytest.raises(DomainError):
            await ConfirmCustomerPhoneChangeUseCase(uow).execute(
                ConfirmCustomerPhoneChangeCommand(token="нет-такого", **_contact("+79280000001"))
            )
