"""Список магазинов GET /api/admin/tenants с агрегатами (A2).

Границы health проверяются на чистой функции домена — сдвигать даты продаж
в БД ради каждого порога дороже и хрупче, а формула одна и та же.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.platform.health import TenantHealth, tenant_health
from tests.test_admin import _admin_headers

TENANTS_URL = "/api/admin/tenants"
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
async def admin_client_headers(client) -> dict:
    return await _admin_headers(client)


@pytest.mark.parametrize(
    "created_days_ago, last_sale_days_ago, expected",
    [
        # магазин без продаж: неделя на первую продажу, дальше — бросил
        (1, None, TenantHealth.NEW),
        (6, None, TenantHealth.NEW),
        (7, None, TenantHealth.CHURNED),
        (30, None, TenantHealth.CHURNED),
        # с продажами: 3 дня активен, 4-14 затих, дальше бросил
        (30, 0, TenantHealth.ACTIVE),
        (30, 3, TenantHealth.ACTIVE),
        (30, 4, TenantHealth.QUIET),
        (30, 14, TenantHealth.QUIET),
        (30, 15, TenantHealth.CHURNED),
    ],
)
def test_health_boundaries(created_days_ago, last_sale_days_ago, expected):
    created = NOW - timedelta(days=created_days_ago)
    last_sale = (
        None if last_sale_days_ago is None else NOW - timedelta(days=last_sale_days_ago)
    )
    assert tenant_health(created, last_sale, NOW) is expected


async def test_tenants_require_admin(client, owner_headers):
    assert (await client.get(TENANTS_URL)).status_code == 401
    assert (await client.get(TENANTS_URL, headers=owner_headers)).status_code == 401


async def test_tenant_list_has_aggregates(client, admin_client_headers, owner_headers):
    response = await client.get(TENANTS_URL, headers=admin_client_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total"] >= 1
    item = body["tenants"][0]
    # агрегаты на месте
    for field in (
        "users_count",
        "warehouses_count",
        "products_count",
        "sales_7d",
        "sales_30d",
        "sales_sum_30d",
        "debts_open_count",
        "storefront_requests_30d",
        "health",
        "owner_name",
        "last_login_at",
    ):
        assert field in item, f"нет поля {field}"

    # владелец только что зарегистрировался и не продавал — новый магазин
    assert item["health"] in {"new", "active", "quiet", "churned"}
    assert item["users_count"] >= 1
    assert body["counts_by_health"]


async def test_shop_without_sales_is_new(client, admin_client_headers, owner_headers):
    body = (await client.get(TENANTS_URL, headers=admin_client_headers)).json()
    fresh = [t for t in body["tenants"] if t["name"] == "Магазин Беркат"]
    assert fresh, "магазин владельца не найден в списке"
    assert fresh[0]["health"] == "new"
    assert fresh[0]["last_sale_at"] is None
    assert fresh[0]["sales_30d"] == 0


async def test_filters_and_search(client, admin_client_headers, owner_headers):
    found = (
        await client.get(f"{TENANTS_URL}?query=беркат", headers=admin_client_headers)
    ).json()
    assert found["total"] >= 1
    assert all("еркат" in t["name"] for t in found["tenants"])

    missing = (
        await client.get(f"{TENANTS_URL}?query=нет-такого", headers=admin_client_headers)
    ).json()
    assert missing["total"] == 0
    assert missing["tenants"] == []

    # витрина у свежего магазина выключена
    off = (
        await client.get(f"{TENANTS_URL}?storefront=off", headers=admin_client_headers)
    ).json()
    assert all(t["storefront_enabled"] is False for t in off["tenants"])

    by_status = (
        await client.get(f"{TENANTS_URL}?status=new", headers=admin_client_headers)
    ).json()
    assert all(t["health"] == "new" for t in by_status["tenants"])


async def test_pagination(client, admin_client_headers, owner_headers, second_shop):
    page = (await client.get(f"{TENANTS_URL}?limit=1", headers=admin_client_headers)).json()
    assert page["total"] >= 2
    assert len(page["tenants"]) == 1

    second = (
        await client.get(f"{TENANTS_URL}?limit=1&offset=1", headers=admin_client_headers)
    ).json()
    assert len(second["tenants"]) == 1
    assert second["tenants"][0]["id"] != page["tenants"][0]["id"]


async def test_no_private_data_in_list(client, admin_client_headers, owner_headers):
    """Админ видит счётчики, но не содержимое чужого бизнеса."""
    raw = (await client.get(TENANTS_URL, headers=admin_client_headers)).text
    for forbidden in ("purchase_price", "debts_open_sum", "client_name", "customer_phone"):
        assert forbidden not in raw, f"в списке не должно быть {forbidden}"


@pytest.fixture
async def second_shop(client, random_phone) -> dict:
    response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Второй магазин",
            "owner_name": "Магомед",
            "phone": random_phone(),
            "password": "secret123",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
