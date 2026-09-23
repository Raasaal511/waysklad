"""Маркетплейс выключен флагом MARKETPLACE_ENABLED (дефолт в проде — false):
все /api/marketplace/* отдают 404, как несуществующие пути.

conftest.py включает флаг для остальных тестов (код маркетплейса жив и
покрыт), поэтому здесь приложение собирается вручную — с тем же набором
роутеров, но при settings.marketplace_enabled=False.
"""

import importlib

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.infrastructure.config import settings

MARKETPLACE_PATHS = [
    "/api/marketplace/products",
    "/api/marketplace/categories",
    "/api/marketplace/cities",
    "/api/marketplace/products/1",
    "/api/marketplace/home",
    "/api/marketplace/shops",
    "/api/marketplace/suggest?q=шуруп",
]


@pytest.fixture
async def disabled_client(monkeypatch) -> AsyncClient:
    monkeypatch.setattr(settings, "marketplace_enabled", False)
    # app/__init__.py собирает router на импорте — перечитываем модуль,
    # чтобы include_router(marketplace_router) не выполнился
    app_module = importlib.reload(importlib.import_module("app"))
    try:
        disabled_app = FastAPI()
        disabled_app.include_router(app_module.router)
        transport = ASGITransport(app=disabled_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        # вернуть общий модуль в состояние «маркетплейс подключён» —
        # иначе остальные тесты сессии увидят урезанный router
        monkeypatch.undo()
        importlib.reload(app_module)


@pytest.mark.parametrize("path", MARKETPLACE_PATHS)
async def test_marketplace_endpoints_return_404_when_disabled(disabled_client, path):
    response = await disabled_client.get(path)
    assert response.status_code == 404


async def test_storefront_similar_marketplace_scope_404_when_disabled(disabled_client):
    """Межмагазинный блок «похожие товары в других магазинах» — часть
    маркетплейса, поэтому тоже закрыт флагом, а scope=shop продолжает жить."""
    response = await disabled_client.get(
        "/api/storefront/any-shop/products/1/similar?scope=marketplace"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Маркетплейс недоступен"
