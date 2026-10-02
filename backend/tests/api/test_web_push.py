import asyncio

import pytest

from app.application.tasks.notify import notify_user
from app.domain.notifications.entities import NotificationKind
from app.domain.notifications.push import PushDeliveryResult, PushMessage, PushSubscription
from app.infrastructure.background import drain
from app.infrastructure.notifications import web_push
from app.infrastructure.security import decode_access_token
from tests.conftest import register_via_bot

FCM = "https://fcm.googleapis.com/fcm/send/"
KEYS = {"p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM", "auth": "tBHItJI5svbpez7KI4CCXg"}


class FakePushSender:
    """Вместо Google/Apple: запоминает отправленное, отвечает заданным результатом."""

    public_key = "BFakePublicKeyForTests"

    def __init__(self):
        self.sent: list[tuple[str, PushMessage]] = []
        self.result = PushDeliveryResult.DELIVERED

    async def send(self, subscription: PushSubscription, message: PushMessage) -> PushDeliveryResult:
        self.sent.append((subscription.endpoint, message))
        return self.result


@pytest.fixture
def push(monkeypatch) -> FakePushSender:
    sender = FakePushSender()
    monkeypatch.setattr(web_push, "push_sender", sender)
    return sender


async def _subscribe(client, headers, endpoint: str):
    return await client.put(
        "/api/notifications/push/subscription",
        headers=headers,
        json={"endpoint": endpoint, "keys": KEYS},
    )


async def _me(client, headers) -> dict:
    """id пользователя и магазина — из его же токена (в /me магазина нет)."""
    payload = decode_access_token(headers["Authorization"].removeprefix("Bearer "))
    return {"id": int(payload["sub"]), "tenant_id": payload["tenant_id"]}


async def _second_owner(client, random_phone) -> dict:
    """Второй магазин — тем же путём, что и живой владелец (через бота)."""
    response = await register_via_bot(
        client,
        {
            "shop_name": "Второй магазин",
            "owner_name": "Магомед",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": True,
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _notify(make_uow, tenant_id: int, user_id: int, *, entity_id: int = 7) -> None:
    async with make_uow(tenant_id) as uow:
        await notify_user(
            uow, None,
            user_id=user_id,
            kind=NotificationKind.LOW_STOCK,
            text="Заканчивается «Мука»: остаток 2 (порог 5)",
            link=f"/products/{entity_id}",
            entity_id=entity_id,
        )
        await uow.commit()
    await drain()  # push уходит после commit в фоне


async def test_push_disabled_without_vapid_key(client, owner_headers):
    """Без ключа на сервере карточка в профиле не показывается, а подписка —
    понятная ошибка, а не тихо сохранённая строка, по которой ничего не придёт."""
    response = await client.get("/api/notifications/push/key", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"public_key": None}

    response = await _subscribe(client, owner_headers, FCM + "abc")
    assert response.status_code == 400, response.text


async def test_new_storefront_request_reaches_phone(client, owner_headers, customer_headers, push):
    buyer_headers, _ = await customer_headers()
    assert (await client.get("/api/notifications/push/key", headers=owner_headers)).json() == {
        "public_key": FakePushSender.public_key
    }
    response = await _subscribe(client, owner_headers, FCM + "owner-phone")
    assert response.status_code == 204, response.text

    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Мука", "purchase_price": "50", "retail_price": "120"},
        )
    ).json()
    await client.put(
        f"/api/products/{product['id']}",
        headers=owner_headers,
        json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
    )
    response = await client.post(
        "/api/storefront/magazin-berkat/requests",
        headers=buyer_headers,
        json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "2"}]},
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]
    await drain()

    assert len(push.sent) == 1
    endpoint, message = push.sent[0]
    assert endpoint == FCM + "owner-phone"
    assert message.title == "Новая заявка с витрины"
    # заголовок не повторяется в тексте — на экране блокировки только суть
    assert message.body == "Ахмед, 1 товар на сумму 240 ₽"
    assert message.link == "/orders/storefront-requests"
    assert message.tag == f"storefront_request_new:{request_id}"
    assert message.urgent is True


async def test_resubscribe_is_idempotent_and_device_moves_to_new_user(
    client, owner_headers, random_phone, make_uow, push
):
    """Кабинет сверяет подписку при каждом открытии — дублей быть не должно.
    Тот же браузер, вошедший в другой магазин, уносит подписку с собой: прежний
    владелец больше не получает уведомлений на чужой телефон."""
    other_headers = await _second_owner(client, random_phone)
    first, other = await _me(client, owner_headers), await _me(client, other_headers)

    assert (await _subscribe(client, owner_headers, FCM + "shared")).status_code == 204
    assert (await _subscribe(client, owner_headers, FCM + "shared")).status_code == 204
    await _notify(make_uow, first["tenant_id"], first["id"])
    assert len(push.sent) == 1

    assert (await _subscribe(client, other_headers, FCM + "shared")).status_code == 204
    push.sent.clear()
    await _notify(make_uow, first["tenant_id"], first["id"])
    assert push.sent == []
    await _notify(make_uow, other["tenant_id"], other["id"])
    assert [e for e, _ in push.sent] == [FCM + "shared"]


async def test_unsubscribe_only_own_device(client, owner_headers, random_phone, make_uow, push):
    other_headers = await _second_owner(client, random_phone)
    me = await _me(client, owner_headers)
    await _subscribe(client, owner_headers, FCM + "mine")

    # чужой endpoint снять нельзя — запрос проходит, но подписка остаётся
    response = await client.post(
        "/api/notifications/push/unsubscribe", headers=other_headers, json={"endpoint": FCM + "mine"}
    )
    assert response.status_code == 204, response.text
    await _notify(make_uow, me["tenant_id"], me["id"])
    assert len(push.sent) == 1

    response = await client.post(
        "/api/notifications/push/unsubscribe", headers=owner_headers, json={"endpoint": FCM + "mine"}
    )
    assert response.status_code == 204, response.text
    push.sent.clear()
    await _notify(make_uow, me["tenant_id"], me["id"])
    assert push.sent == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/abc",  # не https
        "https://10.0.0.5/push",  # IP вместо домена
        "https://[::1]/push",
        "https://redis:6379/x",  # имя из docker-сети
        "https://backend.internal/x",
        "https://user:pass@fcm.googleapis.com/x",
        "ftp://fcm.googleapis.com/x",
        "https://fcm.googleapis.com/" + "a" * 1100,
    ],
)
async def test_subscription_endpoint_must_be_public_https(client, owner_headers, push, endpoint):
    response = await _subscribe(client, owner_headers, endpoint)
    assert response.status_code in (400, 422), response.text


async def test_subscription_keys_validated(client, owner_headers, push):
    response = await client.put(
        "/api/notifications/push/subscription",
        headers=owner_headers,
        json={"endpoint": FCM + "x", "keys": {"p256dh": "not base64!", "auth": "abc"}},
    )
    assert response.status_code == 400, response.text


async def test_gone_subscription_is_removed(client, owner_headers, make_uow, push):
    """Браузер отписался или приложение удалили — push-сервис отвечает 410,
    и дальше на этот адрес не стучимся."""
    me = await _me(client, owner_headers)
    await _subscribe(client, owner_headers, FCM + "deleted-app")

    push.result = PushDeliveryResult.GONE
    await _notify(make_uow, me["tenant_id"], me["id"])
    assert len(push.sent) == 1

    push.result = PushDeliveryResult.DELIVERED
    push.sent.clear()
    await _notify(make_uow, me["tenant_id"], me["id"], entity_id=8)
    assert push.sent == []


async def test_failed_delivery_keeps_subscription(client, owner_headers, make_uow, push):
    me = await _me(client, owner_headers)
    await _subscribe(client, owner_headers, FCM + "flaky")

    push.result = PushDeliveryResult.FAILED
    await _notify(make_uow, me["tenant_id"], me["id"])
    push.result = PushDeliveryResult.DELIVERED
    await _notify(make_uow, me["tenant_id"], me["id"], entity_id=8)
    assert len(push.sent) == 2


async def test_sender_crash_does_not_break_notification(client, owner_headers, make_uow, push):
    """Ошибка отправщика не должна откатить операцию, в которой родилось уведомление."""
    me = await _me(client, owner_headers)
    await _subscribe(client, owner_headers, FCM + "crash")

    async def boom(subscription, message):
        raise RuntimeError("push service down")

    push.send = boom
    await _notify(make_uow, me["tenant_id"], me["id"])
    items = (await client.get("/api/notifications", headers=owner_headers)).json()["items"]
    assert [n["kind"] for n in items] == ["low_stock"]


async def test_logout_all_stops_push_to_old_devices(client, owner_headers, make_uow, push):
    """«Завершить все сессии» (и смена пароля) — уведомления не должны дальше
    уходить на потерянный телефон, где кабинет остался подписан."""
    me = await _me(client, owner_headers)
    await _subscribe(client, owner_headers, FCM + "lost-phone")

    response = await client.post("/api/auth/me/logout-all", headers=owner_headers)
    assert response.status_code == 204, response.text

    await _notify(make_uow, me["tenant_id"], me["id"])
    assert push.sent == []
    async with make_uow(me["tenant_id"]) as uow:
        assert await uow.push_subscriptions.list_for_user(me["id"]) == []


async def test_test_push_goes_only_to_this_device(client, owner_headers, push):
    await _subscribe(client, owner_headers, FCM + "phone")
    await _subscribe(client, owner_headers, FCM + "laptop")

    response = await client.post(
        "/api/notifications/push/test", headers=owner_headers, json={"endpoint": FCM + "phone"}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"delivered": True}
    assert [e for e, _ in push.sent] == [FCM + "phone"]
    assert push.sent[0][1].title == "Уведомления включены"

    # push-сервис не принял — кабинет должен честно сказать, что не дошло
    push.result = PushDeliveryResult.FAILED
    response = await client.post(
        "/api/notifications/push/test", headers=owner_headers, json={"endpoint": FCM + "phone"}
    )
    assert response.json() == {"delivered": False}

    # чужой/неизвестный endpoint — ничего не отправляем
    push.sent.clear()
    response = await client.post(
        "/api/notifications/push/test", headers=owner_headers, json={"endpoint": FCM + "unknown"}
    )
    assert response.json() == {"delivered": False}
    assert push.sent == []


async def test_rolled_back_operation_sends_nothing(client, owner_headers, make_uow, push):
    """Push уходит только после commit: откатившаяся заявка не должна звенеть
    на телефоне владельца."""
    me = await _me(client, owner_headers)
    await _subscribe(client, owner_headers, FCM + "phone")
    async with make_uow(me["tenant_id"]) as uow:
        await notify_user(
            uow, None, user_id=me["id"], kind=NotificationKind.LOW_STOCK, text="t", entity_id=1
        )
        await uow.rollback()
    await drain()
    assert push.sent == []


async def test_two_tabs_confirm_same_subscription_at_once(client, owner_headers, make_uow, push):
    """Две вкладки кабинета подтверждают подписку одновременно — без 500 и без дублей."""
    me = await _me(client, owner_headers)
    responses = await asyncio.gather(
        *(_subscribe(client, owner_headers, FCM + "same") for _ in range(4))
    )
    assert [r.status_code for r in responses] == [204] * 4
    async with make_uow(me["tenant_id"]) as uow:
        assert len(await uow.push_subscriptions.list_for_user(me["id"])) == 1


async def test_device_limit_forgets_longest_unopened(client, owner_headers, make_uow, push):
    """Больше 10 устройств — забываем то, где кабинет дольше всех не открывали,
    а не то, что подписалось раньше всех."""
    me = await _me(client, owner_headers)
    for i in range(10):
        await _subscribe(client, owner_headers, FCM + f"device-{i}")
    # устройство 0 открыли снова — оно свежее остальных
    await _subscribe(client, owner_headers, FCM + "device-0")
    await _subscribe(client, owner_headers, FCM + "device-10")

    async with make_uow(me["tenant_id"]) as uow:
        endpoints = {s.endpoint for s in await uow.push_subscriptions.list_for_user(me["id"])}
    assert len(endpoints) == 10
    assert FCM + "device-0" in endpoints
    assert FCM + "device-10" in endpoints
    assert FCM + "device-1" not in endpoints
