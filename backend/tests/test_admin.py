"""Приватный admin API (/api/admin/*) — статус сервера и лог ошибок,
доступен по X-Admin-Token, а не JWT/Role (см. presentation/deps/admin.py)."""

from app.infrastructure.admin_alerts import report_unhandled_error

_ADMIN_TOKEN = "test-admin-token"  # см. tests/conftest.py: os.environ["ADMIN_API_TOKEN"]


async def test_admin_status_requires_token(client):
    response = await client.get("/api/admin/status")
    assert response.status_code == 403, response.text


async def test_admin_status_rejects_wrong_token(client):
    response = await client.get(
        "/api/admin/status", headers={"X-Admin-Token": "wrong-token"}
    )
    assert response.status_code == 403, response.text


async def test_admin_status_with_valid_token(client):
    response = await client.get(
        "/api/admin/status", headers={"X-Admin-Token": _ADMIN_TOKEN}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["db_connected"] is True
    assert body["redis_connected"] is True
    assert isinstance(body["active_users"], int)
    assert isinstance(body["active_tenants"], int)
    assert isinstance(body["online_now"], int)


async def test_admin_error_logs_requires_token(client):
    response = await client.get("/api/admin/error-logs")
    assert response.status_code == 403, response.text


async def test_admin_error_logs_with_valid_token(client):
    response = await client.get(
        "/api/admin/error-logs", headers={"X-Admin-Token": _ADMIN_TOKEN}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"errors": []}


async def test_admin_error_logs_records_unhandled_error(client):
    await report_unhandled_error("GET", "/api/test/boom", ValueError("что-то сломалось"))

    response = await client.get(
        "/api/admin/error-logs", headers={"X-Admin-Token": _ADMIN_TOKEN}
    )
    assert response.status_code == 200, response.text
    errors = response.json()["errors"]
    assert len(errors) >= 1
    latest = errors[0]  # LPUSH — последняя запись первая
    assert latest["method"] == "GET"
    assert latest["path"] == "/api/test/boom"
    assert latest["error_type"] == "ValueError"
    assert latest["message"] == "что-то сломалось"
