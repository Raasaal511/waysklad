"""Чаты покупателя по JWT (A8).

Главное здесь — изоляция: доступ даёт аккаунт, а не знание id заявки.
"""

from tests.api.test_customer_my_requests import create_request, prepare_shop

CHATS_URL = "/api/auth/customer/chats"


async def test_chat_roundtrip(client, owner_headers, customer_headers):
    buyer_headers, _ = await customer_headers()
    product = await prepare_shop(client, owner_headers)
    request_id = await create_request(client, buyer_headers, product["id"])

    # пустой диалог в списке не показывается
    assert (await client.get(CHATS_URL, headers=buyer_headers)).json() == []

    sent = await client.post(
        f"{CHATS_URL}/{request_id}", headers=buyer_headers, json={"text": "Когда будет готово?"}
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["author"] == "customer"

    messages = await client.get(f"{CHATS_URL}/{request_id}", headers=buyer_headers)
    assert messages.status_code == 200, messages.text
    assert [m["text"] for m in messages.json()] == ["Когда будет готово?"]

    chats = (await client.get(CHATS_URL, headers=buyer_headers)).json()
    assert len(chats) == 1
    assert chats[0]["request_id"] == request_id
    assert chats[0]["shop_name"] == "Магазин Беркат"
    assert chats[0]["last_message"] == "Когда будет готово?"
    assert chats[0]["last_message_from_shop"] is False
    assert chats[0]["messages_count"] == 1


async def test_shop_reply_visible_to_customer(client, owner_headers, customer_headers):
    buyer_headers, _ = await customer_headers()
    product = await prepare_shop(client, owner_headers)
    request_id = await create_request(client, buyer_headers, product["id"])

    await client.post(f"{CHATS_URL}/{request_id}", headers=buyer_headers, json={"text": "Здравствуйте"})
    reply = await client.post(
        f"/api/storefront/requests/{request_id}/chat",
        headers=owner_headers,
        json={"text": "Готово завтра"},
    )
    assert reply.status_code == 201, reply.text

    chats = (await client.get(CHATS_URL, headers=buyer_headers)).json()
    assert chats[0]["last_message"] == "Готово завтра"
    assert chats[0]["last_message_from_shop"] is True
    assert chats[0]["messages_count"] == 2


async def test_foreign_chat_denied(client, owner_headers, customer_headers):
    """Знание id чужой заявки доступа не даёт — проверяется владение аккаунтом."""
    buyer_headers, _ = await customer_headers()
    stranger_headers, _ = await customer_headers()
    product = await prepare_shop(client, owner_headers)
    request_id = await create_request(client, buyer_headers, product["id"])

    read = await client.get(f"{CHATS_URL}/{request_id}", headers=stranger_headers)
    assert read.status_code == 403, read.text

    write = await client.post(
        f"{CHATS_URL}/{request_id}", headers=stranger_headers, json={"text": "Подслушиваю"}
    )
    assert write.status_code == 403, write.text

    # у чужого покупателя список чатов пуст
    assert (await client.get(CHATS_URL, headers=stranger_headers)).json() == []


async def test_missing_request_returns_404(client, customer_headers):
    headers, _ = await customer_headers()
    response = await client.get(f"{CHATS_URL}/999999", headers=headers)
    assert response.status_code == 404


async def test_chats_require_auth(client):
    assert (await client.get(CHATS_URL)).status_code == 401
