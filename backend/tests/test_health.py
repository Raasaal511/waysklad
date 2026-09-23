async def test_health_ok_with_real_db_and_cache(client) -> None:
    # фикстура client уже подменяет БД/кеш на тестовые (dependency_overrides,
    # см. conftest.py) — оба реально доступны в тестовом окружении
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True, "cache": True}


async def test_health_degraded_when_db_down(client) -> None:
    from app.main import app as fastapi_app
    from app.presentation.deps.session import get_session_factory

    class _BrokenSessionFactory:
        def __call__(self):
            raise RuntimeError("БД недоступна (имитация для теста)")

    fastapi_app.dependency_overrides[get_session_factory] = lambda: _BrokenSessionFactory()
    try:
        response = await client.get("/api/health")
    finally:
        del fastapi_app.dependency_overrides[get_session_factory]

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] is False
