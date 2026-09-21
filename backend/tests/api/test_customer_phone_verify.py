"""Подтверждение телефона покупателя кодом (A2, A3).

Код в тестах читается из БД (хеш сверяется bcrypt'ом, самого кода нигде нет) —
отправку подменяем ConsoleCodeSender, чтобы не ходить в Telegram.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.application.customers.request_phone_code import (
    RequestPhoneCodeCommand,
    RequestPhoneCodeUseCase,
)
from app.infrastructure.db.models.customers import CustomerPhoneCodeModel
from app.infrastructure.notifications.code_senders import ConsoleCodeSender
from app.infrastructure.security import hash_password
from app.presentation.deps.use_cases import get_request_phone_code
from app.main import app as fastapi_app

REQUEST_URL = "/api/auth/customer/phone/request-code"
VERIFY_URL = "/api/auth/customer/phone/verify"


@pytest.fixture(autouse=True)
def console_sender(db_session_factory):
    """Коды «отправляются» в лог: тестам нужен только факт выпуска."""
    from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

    def override():
        return RequestPhoneCodeUseCase(
            SqlAlchemyUnitOfWork(None, session_factory=db_session_factory),
            ConsoleCodeSender(),
        )

    fastapi_app.dependency_overrides[get_request_phone_code] = override
    yield
    fastapi_app.dependency_overrides.pop(get_request_phone_code, None)


@pytest.fixture
def customer_id(client):
    """id покупателя по его заголовкам — фикстура customer_headers отдаёт
    только (headers, phone), а тестам нужен id для доступа к коду в БД."""

    async def resolve(headers: dict) -> int:
        response = await client.get("/api/auth/customer/me", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["id"]

    return resolve


async def set_code(make_uow, customer_id: int, code: str, **fields) -> None:
    """Подменяет действующий код известным значением — иначе его не узнать."""
    async with make_uow() as uow:
        model = (
            await uow.session.execute(
                select(CustomerPhoneCodeModel)
                .where(CustomerPhoneCodeModel.customer_id == customer_id)
                .order_by(CustomerPhoneCodeModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        model.code_hash = hash_password(code)
        for key, value in fields.items():
            setattr(model, key, value)
        await uow.commit()


async def test_request_and_verify(client, customer_headers, make_uow, customer_id):
    headers, _ = await customer_headers()
    cid = await customer_id(headers)

    response = await client.post(REQUEST_URL, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["sent_via"] == "console"
    assert response.json()["retry_after"] == 60

    await set_code(make_uow, cid, "123456")

    ok = await client.post(VERIFY_URL, headers=headers, json={"code": "123456"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["phone_verified"] is True
    assert ok.json()["phone_verified_at"]

    # повторное подтверждение — уже нечего подтверждать
    again = await client.post(VERIFY_URL, headers=headers, json={"code": "123456"})
    assert again.status_code == 400
    assert again.json()["detail"] == "Телефон уже подтверждён"


async def test_resend_blocked_within_cooldown(client, customer_headers):
    headers, _ = await customer_headers()
    first = await client.post(REQUEST_URL, headers=headers)
    assert first.status_code == 200

    second = await client.post(REQUEST_URL, headers=headers)
    assert second.status_code == 429, second.text
    assert second.json()["retry_after"] > 0
    assert second.headers["Retry-After"]


async def test_expired_code_rejected(client, customer_headers, make_uow, customer_id):
    headers, _ = await customer_headers()
    cid = await customer_id(headers)
    await client.post(REQUEST_URL, headers=headers)
    await set_code(
        make_uow,
        cid,
        "123456",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    response = await client.post(VERIFY_URL, headers=headers, json={"code": "123456"})
    assert response.status_code == 400
    assert "просрочен" in response.json()["detail"]


async def test_wrong_code_counts_attempts(client, customer_headers, make_uow, customer_id):
    headers, _ = await customer_headers()
    cid = await customer_id(headers)
    await client.post(REQUEST_URL, headers=headers)
    await set_code(make_uow, cid, "123456")

    # пять неверных попыток: последняя переводит в 429
    for expected_left in (4, 3, 2, 1):
        response = await client.post(VERIFY_URL, headers=headers, json={"code": "000000"})
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == f"Неверный код, осталось попыток: {expected_left}"

    last = await client.post(VERIFY_URL, headers=headers, json={"code": "000000"})
    assert last.status_code == 429, last.text

    # верный код больше не принимается — попытки исчерпаны
    correct = await client.post(VERIFY_URL, headers=headers, json={"code": "123456"})
    assert correct.status_code == 429


async def test_hourly_limit(client, customer_headers, make_uow, customer_id):
    headers, _ = await customer_headers()
    cid = await customer_id(headers)

    # пять выпусков подряд: cooldown обходим, сдвигая created_at в прошлое
    for _ in range(5):
        response = await client.post(REQUEST_URL, headers=headers)
        assert response.status_code == 200, response.text
        async with make_uow() as uow:
            model = (
                await uow.session.execute(
                    select(CustomerPhoneCodeModel)
                    .where(CustomerPhoneCodeModel.customer_id == cid)
                    .order_by(CustomerPhoneCodeModel.created_at.desc())
                    .limit(1)
                )
            ).scalar_one()
            # сдвигаем назад только cooldown, оставаясь в пределах часа
            model.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
            await uow.commit()

    # все пять «свежие» в пределах часа — шестой запрос отклоняется
    response = await client.post(REQUEST_URL, headers=headers)
    assert response.status_code == 429, response.text
    assert "через час" in response.json()["detail"]


async def test_code_not_stored_in_plain_text(client, customer_headers, make_uow, customer_id):
    headers, _ = await customer_headers()
    cid = await customer_id(headers)
    await client.post(REQUEST_URL, headers=headers)

    async with make_uow() as uow:
        model = (
            await uow.session.execute(
                select(CustomerPhoneCodeModel)
                .where(CustomerPhoneCodeModel.customer_id == cid)
                .order_by(CustomerPhoneCodeModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
    # bcrypt-хеш, а не шесть цифр
    assert model.code_hash.startswith("$2")
    assert not model.code_hash.isdigit()
