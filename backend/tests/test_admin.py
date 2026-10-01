"""Приватный admin API (/api/admin/*) — логин по логину/паролю
(POST /api/admin/login), не JWT/Role обычного пользователя, не User внутри
tenant (см. presentation/deps/admin.py)."""

from app.infrastructure.observability.admin_alerts import report_unhandled_error
from tests.conftest import register_via_bot

_LOGIN = "test-admin"  # см. tests/conftest.py: os.environ["ADMIN_LOGIN"]
_PASSWORD = "test-admin-password"  # соответствует ADMIN_PASSWORD_HASH в conftest.py


async def _admin_headers(client) -> dict:
    response = await client.post(
        "/api/admin/login", json={"login": _LOGIN, "password": _PASSWORD}
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_admin_login_wrong_password(client):
    response = await client.post(
        "/api/admin/login", json={"login": _LOGIN, "password": "wrong"}
    )
    assert response.status_code == 401, response.text


async def test_admin_login_wrong_login(client):
    response = await client.post(
        "/api/admin/login", json={"login": "someone-else", "password": _PASSWORD}
    )
    assert response.status_code == 401, response.text


async def test_admin_login_success(client):
    response = await client.post(
        "/api/admin/login", json={"login": _LOGIN, "password": _PASSWORD}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"]
    assert body["expires_in_minutes"] > 0


async def test_admin_status_requires_token(client):
    response = await client.get("/api/admin/status")
    assert response.status_code == 401, response.text


async def test_admin_status_rejects_wrong_token(client):
    response = await client.get(
        "/api/admin/status", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401, response.text


async def test_admin_status_with_valid_token(client):
    headers = await _admin_headers(client)
    response = await client.get("/api/admin/status", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["db_connected"] is True
    assert body["redis_connected"] is True
    assert isinstance(body["active_users"], int)
    assert isinstance(body["active_tenants"], int)
    assert isinstance(body["online_now"], int)
    assert isinstance(body["cpu_percent"], (int, float))
    assert isinstance(body["memory_percent"], (int, float))
    assert body["memory_used_mb"] > 0
    assert body["memory_total_mb"] >= body["memory_used_mb"]
    assert isinstance(body["disk_percent"], (int, float))
    assert body["disk_total_gb"] >= body["disk_used_gb"] > 0
    assert isinstance(body["recent_tenants"], list)
    assert isinstance(body["history"], list)
    if body["history"]:
        point = body["history"][0]
        assert set(point.keys()) == {"ts", "cpu_percent", "memory_percent"}


async def test_admin_error_logs_requires_token(client):
    response = await client.get("/api/admin/error-logs")
    assert response.status_code == 401, response.text


async def test_admin_error_logs_with_valid_token(client):
    headers = await _admin_headers(client)
    response = await client.get("/api/admin/error-logs", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"errors": []}


async def test_admin_error_logs_records_unhandled_error(client):
    await report_unhandled_error("GET", "/api/test/boom", ValueError("что-то сломалось"))

    headers = await _admin_headers(client)
    response = await client.get("/api/admin/error-logs", headers=headers)
    assert response.status_code == 200, response.text
    errors = response.json()["errors"]
    assert len(errors) >= 1
    latest = errors[0]  # LPUSH — последняя запись первая
    assert latest["method"] == "GET"
    assert latest["path"] == "/api/test/boom"
    assert latest["error_type"] == "ValueError"
    assert latest["message"] == "что-то сломалось"


async def test_admin_error_logs_hide_sql_details(client):
    """SQL-ошибки (ProgrammingError и т.п.) не должны утекать в лог с текстом
    запроса/параметров — только человеческое сообщение без деталей схемы БД."""
    from sqlalchemy.exc import ProgrammingError

    exc = ProgrammingError(
        "SELECT users.token_version FROM users WHERE users.id = %(id_1)s",
        {"id_1": 3, "tenant_id_1": 3},
        Exception("relation \"users\" does not exist"),
    )
    await report_unhandled_error("GET", "/api/test/sql-boom", exc)

    headers = await _admin_headers(client)
    response = await client.get("/api/admin/error-logs", headers=headers)
    errors = response.json()["errors"]
    latest = errors[0]
    assert latest["path"] == "/api/test/sql-boom"
    assert latest["message"] == "Ошибка базы данных"
    assert "SELECT" not in latest["message"]
    assert "id_1" not in latest["message"]


async def test_admin_status_shows_recent_tenant(client, random_phone):
    register = await register_via_bot(
        client,
        json={
            "shop_name": "Магазин для недавних",
            "owner_name": "Владелец",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": True,
        },
    )
    assert register.status_code == 201, register.text

    headers = await _admin_headers(client)
    response = await client.get("/api/admin/status", headers=headers)
    assert response.status_code == 200, response.text
    names = [t["name"] for t in response.json()["recent_tenants"]]
    assert "Магазин для недавних" in names


async def test_admin_list_and_suspend_tenant(client, random_phone):
    register = await register_via_bot(
        client,
        json={
            "shop_name": "Магазин для теста блокировки",
            "owner_name": "Владелец",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": True,
        },
    )
    assert register.status_code == 201, register.text
    owner_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    owner_phone = register.json()["user"]["phone"]

    headers = await _admin_headers(client)

    list_response = await client.get("/api/admin/tenants", headers=headers)
    assert list_response.status_code == 200, list_response.text
    tenants = list_response.json()["tenants"]
    tenant_id = next(t["id"] for t in tenants if t["name"] == "Магазин для теста блокировки")

    detail_response = await client.get(f"/api/admin/tenants/{tenant_id}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["is_suspended"] is False
    assert detail["owner"]["phone"] == owner_phone
    assert detail["users_count"] == 1

    suspend_response = await client.post(
        f"/api/admin/tenants/{tenant_id}/suspend", headers=headers
    )
    assert suspend_response.status_code == 200, suspend_response.text
    assert suspend_response.json()["is_suspended"] is True

    # уже выданный токен владельца немедленно перестаёт работать
    blocked = await client.get("/api/auth/shop", headers=owner_headers)
    assert blocked.status_code == 403, blocked.text

    # новый логин тоже заблокирован
    login_attempt = await client.post(
        "/api/auth/login", json={"phone": owner_phone, "password": "secret123", "personal_data_consent": True}
    )
    assert login_attempt.status_code == 403, login_attempt.text

    unsuspend_response = await client.post(
        f"/api/admin/tenants/{tenant_id}/unsuspend", headers=headers
    )
    assert unsuspend_response.status_code == 200, unsuspend_response.text
    assert unsuspend_response.json()["is_suspended"] is False

    restored = await client.get("/api/auth/shop", headers=owner_headers)
    assert restored.status_code == 200, restored.text


async def test_admin_suspend_unknown_tenant_returns_404(client):
    headers = await _admin_headers(client)
    response = await client.post("/api/admin/tenants/999999/suspend", headers=headers)
    assert response.status_code == 404, response.text
