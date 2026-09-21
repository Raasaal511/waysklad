import pytest
from pydantic import ValidationError

from app.infrastructure.config import Settings

# database_url/secret_key больше не имеют дефолта (см. config.py) — задаём
# минимальный валидный набор явно в каждом тесте, а не полагаемся на os.environ
# из conftest.py, чтобы тест не зависел от порядка импорта.
_REQUIRED = {"database_url": "postgresql+psycopg://u:p@localhost/db", "secret_key": "test"}


def test_cors_origin_list_empty_by_default():
    assert Settings(cors_origins="", **_REQUIRED).cors_origin_list == []


def test_cors_origin_list_splits_and_strips():
    settings = Settings(cors_origins="https://a.example, https://b.example ,", **_REQUIRED)
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]


def test_database_url_required(monkeypatch):
    # conftest.py задаёт DATABASE_URL/SECRET_KEY в os.environ для остального
    # набора (см. комментарий там) — pydantic-settings читает env как fallback
    # даже с _env_file=None, поэтому здесь их нужно явно снять с окружения.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(secret_key="test", _env_file=None)


def test_secret_key_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+psycopg://u:p@localhost/db", _env_file=None)
