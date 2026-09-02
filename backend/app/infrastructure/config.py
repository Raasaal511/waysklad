from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://waysklad:change-me@localhost:5432/waysklad"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 30
    debug: bool = False
    telegram_bot_token: str = ""
    # chat_id разработчика/оператора — куда шлются алерты о непредвиденных
    # серверных ошибках (500 на sales/debts/sync). Не путать с
    # Tenant.owner_telegram_chat_id — это про владельцев магазинов и сводки.
    admin_alert_chat_id: str = ""
    # выключается в тестах (conftest.py) — иначе повторный логин в одном
    # тестовом сценарии упирается в лимит /auth/login
    rate_limit_enabled: bool = True
    # None (по умолчанию) — in-memory storage: ок для одного процесса (локальная
    # разработка). В проде backend поднят с несколькими uvicorn-воркерами
    # (--workers), и без общего storage у каждого свой независимый счётчик —
    # реальный лимит становится в N раз больше заявленного. Задаётся в .env как
    # redis://redis:6379/0 (см. docker-compose.prod.yml).
    rate_limit_storage_uri: str | None = None
    # None (по умолчанию) — WebSocket-push уведомлений форвардится в памяти
    # процесса: ок для одного uvicorn-воркера (dev, --reload без --workers).
    # В проде (--workers 4) открытое соединение клиента живёт только в одном
    # воркере — без Redis pub/sub уведомление, созданное в другом воркере
    # (другой HTTP-запрос), никогда не дойдёт до открытого сокета. Задаётся в
    # .env как redis://redis:6379/1 (тот же Redis, что и rate limit, другая БД).
    notifications_redis_url: str | None = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
