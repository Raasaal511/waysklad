from fastapi import APIRouter
from fastapi.testclient import TestClient

import app.presentation.errors as errors_module
from app.main import app


def test_unhandled_error_returns_500_and_reports(monkeypatch) -> None:
    # баг в коде/обрыв БД не должен утекать наружу как голый traceback или
    # необработанное соединение — и должен быть замечен (report_unhandled_error)
    reported = []
    monkeypatch.setattr(
        errors_module, "report_unhandled_error",
        lambda method, path, exc: reported.append((method, path, type(exc).__name__)),
    )

    boom_router = APIRouter()

    @boom_router.get("/api/_test_boom")
    def boom():
        raise RuntimeError("непредвиденный баг")

    app.include_router(boom_router)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/_test_boom")
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", None) != "/api/_test_boom"
        ]

    assert response.status_code == 500
    assert response.json() == {"detail": "Внутренняя ошибка сервера"}
    assert reported == [("GET", "/api/_test_boom", "RuntimeError")]
