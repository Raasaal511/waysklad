"""Ошибки сервера в БД: группировка, детали, «решено», чистка (A5).

Отдельно проверяется требование приватности: в записи нет ни тела запроса,
ни заголовков, ни персональных данных.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.application.admin.error_groups import (
    RETENTION_DAYS,
    make_signature,
    record_error,
)
from app.infrastructure.db.models.errors import STACK_MAX_CHARS, ErrorLogModel
from tests.test_admin import _admin_headers

GROUPS_URL = "/api/admin/error-groups"
LOGS_URL = "/api/admin/error-logs"


@pytest.fixture
async def admin_client_headers(client) -> dict:
    return await _admin_headers(client)


def test_signature_collapses_numeric_segments():
    """Одна и та же ошибка на разных id — одна группа, а не сто."""
    a = make_signature("ValueError", "GET", "/api/products/17")
    b = make_signature("ValueError", "GET", "/api/products/42")
    assert a == b

    other_path = make_signature("ValueError", "GET", "/api/sales/17")
    other_type = make_signature("KeyError", "GET", "/api/products/17")
    assert a != other_path
    assert a != other_type


async def test_groups_aggregate_and_sort(client, admin_client_headers, db_session_factory):
    for _ in range(3):
        await record_error(
            db_session_factory,
            error_type="ValueError",
            method="GET",
            path="/api/products/1",
            message="bad value",
        )
    await record_error(
        db_session_factory,
        error_type="KeyError",
        method="POST",
        path="/api/sales",
        message="missing key",
    )

    groups = (await client.get(GROUPS_URL, headers=admin_client_headers)).json()
    assert len(groups) == 2
    # самая частая за сутки — сверху
    assert groups[0]["type"] == "ValueError"
    assert groups[0]["count_24h"] == 3
    assert groups[0]["count_7d"] == 3
    assert groups[0]["method"] == "GET"
    assert groups[0]["resolved"] is False
    assert groups[0]["sample_id"] > 0


async def test_group_entries_and_single_entry(
    client, admin_client_headers, db_session_factory
):
    await record_error(
        db_session_factory,
        error_type="ValueError",
        method="GET",
        path="/api/products/5",
        message="bad value",
        stack="Traceback...\n  line 1",
        status_code=500,
        tenant_id=7,
    )

    groups = (await client.get(GROUPS_URL, headers=admin_client_headers)).json()
    signature = groups[0]["signature"]

    entries = (
        await client.get(f"{GROUPS_URL}/{signature}/entries", headers=admin_client_headers)
    ).json()
    assert len(entries) == 1
    assert entries[0]["message"] == "bad value"

    single = (
        await client.get(f"{LOGS_URL}/{entries[0]['id']}", headers=admin_client_headers)
    ).json()
    assert single["status_code"] == 500
    assert single["tenant_id"] == 7
    assert "Traceback" in single["stack"]


async def test_resolve_moves_group_out_of_list(
    client, admin_client_headers, db_session_factory
):
    await record_error(
        db_session_factory,
        error_type="ValueError",
        method="GET",
        path="/api/products/9",
        message="bad value",
    )
    signature = (await client.get(GROUPS_URL, headers=admin_client_headers)).json()[0][
        "signature"
    ]

    resolved = await client.post(
        f"{GROUPS_URL}/{signature}/resolve", headers=admin_client_headers
    )
    assert resolved.status_code == 200, resolved.text

    # из основного списка ушла
    assert (await client.get(GROUPS_URL, headers=admin_client_headers)).json() == []
    # но видна среди решённых
    all_groups = (
        await client.get(f"{GROUPS_URL}?only_unresolved=false", headers=admin_client_headers)
    ).json()
    assert len(all_groups) == 1
    assert all_groups[0]["resolved"] is True


async def test_resolve_missing_group_is_404(client, admin_client_headers):
    response = await client.post(
        f"{GROUPS_URL}/no-such-signature/resolve", headers=admin_client_headers
    )
    assert response.status_code == 404


async def test_filters(client, admin_client_headers, db_session_factory):
    await record_error(
        db_session_factory,
        error_type="ValueError",
        method="GET",
        path="/api/products/1",
        message="x",
    )
    await record_error(
        db_session_factory,
        error_type="KeyError",
        method="GET",
        path="/api/sales/1",
        message="y",
    )

    by_type = (
        await client.get(f"{GROUPS_URL}?error_type=KeyError", headers=admin_client_headers)
    ).json()
    assert len(by_type) == 1
    assert by_type[0]["type"] == "KeyError"

    by_path = (
        await client.get(f"{GROUPS_URL}?path=products", headers=admin_client_headers)
    ).json()
    assert len(by_path) == 1
    assert "products" in by_path[0]["path"]


async def test_stack_is_truncated(client, admin_client_headers, db_session_factory):
    """Полный трейсбек бывает на десятки килобайт — режем при записи."""
    await record_error(
        db_session_factory,
        error_type="ValueError",
        method="GET",
        path="/api/products/1",
        message="x",
        stack="s" * (STACK_MAX_CHARS + 5000),
    )
    async with db_session_factory() as session:
        model = (await session.execute(select(ErrorLogModel))).scalars().first()
    assert len(model.stack) == STACK_MAX_CHARS


async def test_old_records_are_purged(client, admin_client_headers, db_session_factory):
    """Чистка идёт при записи (планировщика в проекте нет): записи старше
    RETENTION_DAYS удаляются."""
    from app.application.admin import error_groups

    async with db_session_factory() as session:
        session.add(
            ErrorLogModel(
                signature="old",
                error_type="OldError",
                method="GET",
                path="/api/old",
                message="old",
                stack="",
                created_at=datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS + 1),
            )
        )
        await session.commit()

    # чистка вероятностная — на время теста делаем её гарантированной
    error_groups._PURGE_CHANCE = 1.0
    try:
        await record_error(
            db_session_factory,
            error_type="ValueError",
            method="GET",
            path="/api/products/1",
            message="fresh",
        )
    finally:
        error_groups._PURGE_CHANCE = 0.01

    async with db_session_factory() as session:
        rows = (await session.execute(select(ErrorLogModel.error_type))).scalars().all()
    assert "OldError" not in rows
    assert "ValueError" in rows


async def test_no_personal_data_stored(client, admin_client_headers, db_session_factory):
    """В таблице нет колонок под тело запроса, заголовки и персональные данные."""
    columns = set(ErrorLogModel.__table__.columns.keys())
    for forbidden in ("body", "headers", "authorization", "phone", "params", "cookies"):
        assert forbidden not in columns, f"колонка {forbidden} не должна существовать"

    await record_error(
        db_session_factory,
        error_type="ValueError",
        method="GET",
        path="/api/products/1",
        message="x",
    )
    raw = (await client.get(GROUPS_URL, headers=admin_client_headers)).text
    for forbidden in ("authorization", "cookie", "password"):
        assert forbidden not in raw.lower()


async def test_error_endpoints_require_admin(client, owner_headers):
    assert (await client.get(GROUPS_URL)).status_code == 401
    assert (await client.get(GROUPS_URL, headers=owner_headers)).status_code == 401
    assert (await client.get(f"{LOGS_URL}/1", headers=owner_headers)).status_code == 401
