"""Состояние сервера GET /api/admin/status, расширение v2 (A4).

Отдельно проверяется главное обещание раздела: чего получить нельзя, то null,
а не выдуманный ноль.
"""

import json

import pytest

from app.infrastructure.observability.api_metrics import (
    BUCKETS_MS,
    ApiMetricsCollector,
    _percentile,
)
from tests.test_admin import _admin_headers

STATUS_URL = "/api/admin/status"


@pytest.fixture
async def admin_client_headers(client) -> dict:
    return await _admin_headers(client)


async def test_status_has_v2_blocks(client, admin_client_headers):
    response = await client.get(STATUS_URL, headers=admin_client_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["app"]["version"]
    assert body["app"]["git_sha"]  # "dev" в локальной сборке
    assert body["app"]["workers"] >= 1

    assert body["db"]["ok"] is True
    assert body["db"]["size_bytes"] > 0
    assert body["db"]["connections_max"] > 0

    assert body["uploads"]["files_count"] >= 0
    assert body["api"] is not None
    assert body["disk_free_percent"] is not None


async def test_missing_status_files_give_null(client, admin_client_headers, tmp_path, monkeypatch):
    """Файлов tls.json/backup.json нет — блоки null, а не нули: «не настроено»
    и «ноль байт» это разные вещи."""
    from app.infrastructure.config import settings

    monkeypatch.setattr(settings, "status_dir", str(tmp_path))
    body = (await client.get(STATUS_URL, headers=admin_client_headers)).json()
    assert body["tls"] is None
    assert body["backup"] is None


async def test_status_files_are_read(client, admin_client_headers, tmp_path, monkeypatch):
    """Backend читает то, что положили внешние скрипты, и не лезет никуда ещё."""
    from app.infrastructure.config import settings

    (tmp_path / "tls.json").write_text(
        json.dumps({"domain": "waysklad.example", "expires_at": "2027-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    (tmp_path / "backup.json").write_text(
        json.dumps({"last_at": "2026-09-21T03:00:00+00:00", "size_bytes": 1024, "offsite_ok": False}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "status_dir", str(tmp_path))

    body = (await client.get(STATUS_URL, headers=admin_client_headers)).json()
    assert body["tls"]["domain"] == "waysklad.example"
    assert body["tls"]["days_left"] > 0
    assert body["backup"]["size_bytes"] == 1024
    # внешней копии нет — говорим об этом честно
    assert body["backup"]["offsite_ok"] is False


async def test_broken_status_file_does_not_break_admin(
    client, admin_client_headers, tmp_path, monkeypatch
):
    from app.infrastructure.config import settings

    (tmp_path / "tls.json").write_text("{не json", encoding="utf-8")
    monkeypatch.setattr(settings, "status_dir", str(tmp_path))

    response = await client.get(STATUS_URL, headers=admin_client_headers)
    assert response.status_code == 200
    assert response.json()["tls"] is None


async def test_status_requires_admin(client, owner_headers):
    assert (await client.get(STATUS_URL)).status_code == 401
    assert (await client.get(STATUS_URL, headers=owner_headers)).status_code == 401


# --- метрики API ---------------------------------------------------------


def test_percentile_picks_bucket():
    # 100 запросов: 90 быстрых, 10 медленных
    histogram = {"5": 90, "1000": 10}
    assert _percentile(histogram, 100, 0.50) == 5
    assert _percentile(histogram, 100, 0.95) == 1000


def test_percentile_empty():
    assert _percentile({}, 0, 0.5) is None


def test_percentile_beyond_last_bucket():
    """Всё дольше последней границы — отдаём её, а не отрицательное число."""
    assert _percentile({"inf": 10}, 10, 0.95) == BUCKETS_MS[-1]


async def test_api_metrics_roundtrip(client, admin_client_headers):
    """Счётчик пишет и читает через общий Redis — тот же путь, что и в проде."""
    from app.main import app as fastapi_app
    from app.presentation.deps.cache import get_cache

    cache = fastapi_app.dependency_overrides[get_cache]()
    collector = ApiMetricsCollector(cache.raw)

    for _ in range(10):
        await collector.record(7.0, 200)
    await collector.record(1500.0, 500)
    await collector.record(30.0, 404)

    metrics = await collector.read()
    assert metrics.rps_1h is not None and metrics.rps_1h > 0
    assert metrics.p50_ms == 10  # корзина, куда попали 7 мс
    assert metrics.errors_5xx_24h == 1
    assert metrics.errors_4xx_24h == 1


async def test_api_metrics_empty_window_is_null(client):
    """Запросов не было — None, а не ноль: «нет данных» и «всё быстро» разное."""
    from app.main import app as fastapi_app
    from app.presentation.deps.cache import get_cache

    cache = fastapi_app.dependency_overrides[get_cache]()
    metrics = await ApiMetricsCollector(cache.raw).read()
    assert metrics.rps_1h is None
    assert metrics.p50_ms is None
    assert metrics.p95_ms is None
