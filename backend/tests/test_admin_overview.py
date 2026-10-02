"""Обзор платформы GET /api/admin/overview (A1).

Отдельно проверяется то, что делает эти агрегаты опасными: они ходят по всем
магазинам сразу. Тесты фиксируют, что такой доступ есть только у админа
платформы, а обычный владелец магазина по-прежнему видит только свой tenant.
"""

import pytest

from tests.test_admin import _admin_headers
from tests.conftest import register_via_bot

OVERVIEW_URL = "/api/admin/overview"


async def _reset_overview_cache() -> None:
    """Кеш обзора живёт 60 секунд — для замера «до и после» его надо сбросить."""
    from app.main import app as fastapi_app
    from app.presentation.deps.cache import get_cache

    cache = fastapi_app.dependency_overrides[get_cache]()
    await cache.delete_prefix("admin:overview")


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
    """Второй магазин — для проверки, что tenant-scoping не ослаб."""
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


async def test_overview_requires_admin(client, owner_headers):
    """Владелец магазина в админку платформы не попадает — ни без токена,
    ни со своим обычным JWT."""
    assert (await client.get(OVERVIEW_URL)).status_code == 401
    assert (await client.get(OVERVIEW_URL, headers=owner_headers)).status_code == 401


async def test_overview_on_empty_platform(client, admin_client_headers):
    """Пустая платформа — нули, а не падение."""
    response = await client.get(OVERVIEW_URL, headers=admin_client_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["shops"]["total"] >= 0
    assert body["sales"]["today_count"] >= 0
    assert body["debts"]["open_count"] >= 0
    # ряды всегда заполнены: 31 день (30 суток назад + сегодня)
    assert len(body["series_30d"]["date"]) == 31
    assert len(body["series_30d"]["sales_count"]) == 31
    assert len(body["series_30d"]["active_shops"]) == 31
    assert len(body["series_30d"]["new_shops"]) == 31


async def test_overview_counts_sales_and_shops(
    client, admin_client_headers, owner_headers, make_sale
):
    """Ответ кешируется на 60 секунд (это и нужно в проде), поэтому между
    двумя замерами кеш сбрасывается явно — иначе тест мерил бы кеш."""
    before = (await client.get(OVERVIEW_URL, headers=admin_client_headers)).json()

    await make_sale(owner_headers, total="500")
    await _reset_overview_cache()

    after = (await client.get(OVERVIEW_URL, headers=admin_client_headers)).json()
    assert after["sales"]["today_count"] == before["sales"]["today_count"] + 1
    assert after["sales"]["d7_count"] == before["sales"]["d7_count"] + 1
    # магазин с продажей считается активным
    assert after["shops"]["active_7d"] >= 1
    assert after["shops"]["total"] >= 1


async def test_overview_debts_are_aggregate_only(
    client, admin_client_headers, owner_headers, make_sale
):
    """Долги — только счётчик и сумма по платформе: ни клиентов, ни телефонов."""
    response = await client.get(OVERVIEW_URL, headers=admin_client_headers)
    debts = response.json()["debts"]
    assert set(debts.keys()) == {"open_count", "open_sum"}

    # во всём ответе нет полей с персональными данными
    raw = response.text
    for forbidden in ("phone", "client_name", "customer_name", "purchase_price"):
        assert forbidden not in raw, f"в обзоре не должно быть поля {forbidden}"


async def test_tenant_isolation_unaffected(client, owner_headers, second_shop_headers):
    """Кросс-тенантные запросы админки не должны ослаблять обычный scoping:
    владелец одного магазина по-прежнему не видит товары другого."""
    mine = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Мой товар", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()

    others = (await client.get("/api/products", headers=second_shop_headers)).json()
    assert all(p["id"] != mine["id"] for p in others)

    # и напрямую по id чужой товар недоступен
    direct = await client.get(f"/api/products/{mine['id']}", headers=second_shop_headers)
    assert direct.status_code == 404
