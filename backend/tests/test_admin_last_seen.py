"""«Был в сети» владельца в админке платформы.

last_login_at меняется только при вводе пароля, а токен живёт неделями —
поэтому отдельный last_seen_at, который сдвигает любой запрос с токеном.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.infrastructure.db.models.identity import UserModel
from app.presentation.deps.auth import LAST_SEEN_STEP
from tests.test_admin import _admin_headers

WAREHOUSES_URL = "/api/inventory/warehouses"


@pytest.fixture
async def admin_client_headers(client) -> dict:
    return await _admin_headers(client)


async def _set_last_seen(factory, at: datetime) -> None:
    async with factory() as session:
        await session.execute(update(UserModel).values(last_seen_at=at))
        await session.commit()


async def _last_seen(factory) -> datetime:
    async with factory() as session:
        return (await session.execute(select(UserModel.last_seen_at))).scalar_one()


async def test_admin_sees_owner_last_seen(client, admin_client_headers, owner_headers):
    # owner_headers уже сделал запрос с токеном (создал склад) — без ввода пароля
    listing = (await client.get("/api/admin/tenants", headers=admin_client_headers)).json()
    item = listing["tenants"][0]
    assert item["owner_last_seen_at"] is not None

    detail = (
        await client.get(f"/api/admin/tenants/{item['id']}", headers=admin_client_headers)
    ).json()
    assert detail["owner"]["last_seen_at"] is not None
    assert detail["users"][0]["last_seen_at"] is not None


async def test_last_seen_written_once_per_step(client, owner_headers, db_session_factory):
    recent = datetime.now(timezone.utc) - timedelta(minutes=1)
    await _set_last_seen(db_session_factory, recent)
    assert (await client.get(WAREHOUSES_URL, headers=owner_headers)).status_code == 200
    # внутри шага не пишем в users на каждый запрос
    assert await _last_seen(db_session_factory) == recent

    stale = datetime.now(timezone.utc) - LAST_SEEN_STEP - timedelta(minutes=1)
    await _set_last_seen(db_session_factory, stale)
    assert (await client.get(WAREHOUSES_URL, headers=owner_headers)).status_code == 200
    assert await _last_seen(db_session_factory) > stale + LAST_SEEN_STEP


async def test_suspended_shop_does_not_count_as_seen(
    client, admin_client_headers, owner_headers, db_session_factory
):
    tenant_id = (
        await client.get("/api/admin/tenants", headers=admin_client_headers)
    ).json()["tenants"][0]["id"]
    suspend = await client.post(
        f"/api/admin/tenants/{tenant_id}/suspend", headers=admin_client_headers
    )
    assert suspend.status_code == 200, suspend.text

    stale = datetime.now(timezone.utc) - timedelta(days=3)
    await _set_last_seen(db_session_factory, stale)
    assert (await client.get(WAREHOUSES_URL, headers=owner_headers)).status_code == 403
    assert await _last_seen(db_session_factory) == stale
