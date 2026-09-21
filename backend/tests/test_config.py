from app.infrastructure.config import Settings


def test_cors_origin_list_empty_by_default():
    assert Settings(cors_origins="").cors_origin_list == []


def test_cors_origin_list_splits_and_strips():
    settings = Settings(cors_origins="https://a.example, https://b.example ,")
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]
