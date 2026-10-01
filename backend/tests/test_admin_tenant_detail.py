"""Карточка магазина GET /api/admin/tenants/{id} (A3).

Главное, что здесь проверяется помимо данных, — приватность: админ платформы
видит счётчики, даты и статусы, но не содержимое чужого бизнеса.
"""

import pytest

from tests.test_admin import _admin_headers
from tests.conftest import register_via_bot

DETAIL_URL = "/api/admin/tenants"


@pytest.fixture
async def admin_client_headers(client) -> dict:
    return await _admin_headers(client)


@pytest.fixture
def make_sale(client):
    """Продажа «как из интерфейса»: товар, приёмка, чек."""

    async def create(headers: dict, total: str = "500") -> dict:
        product = (
            await client.post(
                "/api/products",
                headers=headers,
                json={"name": "Товар", "purchase_price": "50", "retail_price": total},
            )
        ).json()
        await client.post(
            "/api/inventory/receive",
            headers=headers,
            json={
                "warehouse_id": 1,
                "lines": [{"product_id": product["id"], "quantity": "10", "cost": "50"}],
            },
        )
        response = await client.post(
            "/api/sales",
            headers=headers,
            json={
                "warehouse_id": 1,
                "payment_method": "cash",
                "items": [{"product_id": product["id"], "quantity": "1", "price": total}],
                "cash_received": total,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
async def second_shop_headers(client, random_phone) -> dict:
    response = await register_via_bot(
        client,
        json={
            "shop_name": "Другой магазин",
            "owner_name": "Магомед",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": True,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    await client.post("/api/inventory/warehouses", headers=headers, json={"name": "Склад"})
    return headers


@pytest.fixture
async def tenant_id(client, admin_client_headers, owner_headers) -> int:
    body = (await client.get(DETAIL_URL, headers=admin_client_headers)).json()
    mine = [t for t in body["tenants"] if t["name"] == "Магазин Беркат"]
    assert mine, "магазин владельца не найден"
    return mine[0]["id"]


async def test_detail_requires_admin(client, owner_headers, tenant_id):
    assert (await client.get(f"{DETAIL_URL}/{tenant_id}")).status_code == 401
    assert (
        await client.get(f"{DETAIL_URL}/{tenant_id}", headers=owner_headers)
    ).status_code == 401


async def test_detail_missing_tenant(client, admin_client_headers):
    assert (await client.get(f"{DETAIL_URL}/999999", headers=admin_client_headers)).status_code == 404


async def test_detail_has_all_blocks(client, admin_client_headers, tenant_id):
    response = await client.get(f"{DETAIL_URL}/{tenant_id}", headers=admin_client_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["health"]
    assert body["sales_series_30d"] is not None
    # ряд заполнен по дням, включая дни без продаж
    assert len(body["sales_series_30d"]["date"]) == 31
    assert len(body["sales_series_30d"]["count"]) == 31

    assert isinstance(body["users"], list) and body["users"]
    user = body["users"][0]
    assert {"id", "name", "role", "is_active", "last_login_at", "last_seen_at"} == set(user)

    assert isinstance(body["warehouses"], list)
    assert body["storefront"] is not None
    assert body["totals"] is not None
    assert isinstance(body["recent_activity"], list)
    assert isinstance(body["top_products"], list)


async def test_detail_shows_sales(
    client, admin_client_headers, owner_headers, tenant_id, make_sale
):
    await make_sale(owner_headers, total="700")

    body = (
        await client.get(f"{DETAIL_URL}/{tenant_id}", headers=admin_client_headers)
    ).json()
    assert body["sales_30d"] >= 1
    assert body["sales_7d"] >= 1
    assert body["totals"]["sales_all_time"] >= 1
    assert body["health"] == "active"
    # проданный товар попал в топ
    assert body["top_products"]
    assert body["top_products"][0]["sold_30d"]


async def test_detail_hides_private_data(
    client, admin_client_headers, owner_headers, tenant_id, make_sale
):
    """Ни закупочных цен, ни телефонов сотрудников, ни сумм долгов по клиентам,
    ни текстов чатов — только счётчики, даты и статусы."""
    await make_sale(owner_headers, total="700")
    raw = (await client.get(f"{DETAIL_URL}/{tenant_id}", headers=admin_client_headers)).text

    for forbidden in (
        "purchase_price",
        "customer_phone",
        "client_name",
        "debts_open_sum",
        "details",
        "message",
    ):
        assert forbidden not in raw, f"в карточке магазина не должно быть {forbidden}"

    body = (await client.get(f"{DETAIL_URL}/{tenant_id}", headers=admin_client_headers)).json()
    # у сотрудников нет телефона
    assert all("phone" not in u for u in body["users"])
    # долги — только количество
    assert "debts_open_count" in body["totals"]
    assert not any("sum" in k for k in body["totals"])


async def test_detail_is_scoped_to_one_tenant(
    client, admin_client_headers, owner_headers, second_shop_headers, tenant_id, make_sale
):
    """Агрегаты карточки считаются по одному магазину: продажа соседа сюда
    попадать не должна."""
    before = (
        await client.get(f"{DETAIL_URL}/{tenant_id}", headers=admin_client_headers)
    ).json()

    await make_sale(second_shop_headers, total="900")

    after = (
        await client.get(f"{DETAIL_URL}/{tenant_id}", headers=admin_client_headers)
    ).json()
    assert after["sales_30d"] == before["sales_30d"]
    assert after["totals"]["sales_all_time"] == before["totals"]["sales_all_time"]
