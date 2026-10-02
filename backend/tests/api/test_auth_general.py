import pytest
from tests.conftest import register_via_bot


async def test_register_login_flow(client, random_phone):
    phone = random_phone()
    response = await register_via_bot(
        client,
        json={
            "shop_name": "Лавка",
            "owner_name": "Муса",
            "phone": phone,
            "password": "secret123",
            "personal_data_consent": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "owner"
    assert response.json()["shop_slug"] == "lavka"

    response = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "secret123", "personal_data_consent": True}
    )
    assert response.status_code == 200
    assert response.json()["shop_slug"] is None  # слаг возвращается только при регистрации

    response = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "wrong"}
    )
    assert response.status_code == 403

    response = await client.get("/api/products")
    assert response.status_code == 401  # без токена


async def test_register_requires_personal_data_consent(client, random_phone):
    response = await register_via_bot(
        client,
        json={
            "shop_name": "Лавка",
            "owner_name": "Муса",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": False,
        },
    )
    assert response.status_code == 400
    assert "согласи" in response.json()["detail"].lower()

    response = await register_via_bot(
        client,
        json={
            "shop_name": "Лавка",
            "owner_name": "Муса",
            "phone": random_phone(),
            "password": "123",  # короче 6 символов
            "personal_data_consent": True,
        },
    )
    assert response.status_code == 422


async def test_not_found_returns_404(client, owner_headers):
    response = await client.get("/api/products/999999", headers=owner_headers)
    assert response.status_code == 404


async def test_notifications_websocket_push(client, owner_headers, random_phone, db_session_factory):
    # push вместо периодического опроса GET /notifications: задача, назначенная
    # сотруднику, должна прилететь в открытый WS-сокет этого сотрудника сразу
    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Хеда", "phone": phone, "password": "secret123", "role": "seller"},
    )
    employee_id = response.json()["id"]
    login = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123", "personal_data_consent": True})
    employee_token = login.json()["access_token"]

    sync_client = TestClient(fastapi_app)
    with sync_client.websocket_connect(f"/api/notifications/ws?token={employee_token}") as ws:
        response = await client.post(
            "/api/tasks",
            headers=owner_headers,
            json={"title": "Через WS", "assigned_user_id": employee_id},
        )
        assert response.status_code == 201, response.text
        task_id = response.json()["id"]

        event = ws.receive_json()
        assert event["kind"] == "task_assigned"
        assert event["entity_id"] == task_id


async def test_notifications_websocket_rejects_invalid_token(client, owner_headers):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from app.main import app as fastapi_app

    sync_client = TestClient(fastapi_app)
    with pytest.raises(WebSocketDisconnect):
        with sync_client.websocket_connect("/api/notifications/ws?token=garbage"):
            pass


async def test_update_shop_summary_schedule_via_api(client, owner_headers):
    response = await client.get("/api/auth/shop", headers=owner_headers)
    assert response.status_code == 200
    shop = response.json()
    # дефолты сразу после регистрации
    assert shop["summary_daily_enabled"] is True
    assert shop["summary_weekly_enabled"] is False
    assert shop["summary_monthly_enabled"] is False
    assert shop["summary_daily_hour_msk"] == 20

    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={
            "name": shop["name"],
            "summary_weekly_enabled": True,
            "summary_monthly_enabled": True,
            "summary_daily_hour_msk": 9,
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["summary_daily_enabled"] is True  # не тронули — осталось прежним
    assert updated["summary_weekly_enabled"] is True
    assert updated["summary_monthly_enabled"] is True
    assert updated["summary_daily_hour_msk"] == 9

    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": shop["name"], "summary_daily_hour_msk": 24},
    )
    assert response.status_code == 422  # вне диапазона 0..23
