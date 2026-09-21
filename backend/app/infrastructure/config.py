from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Без дефолта намеренно — раньше "postgresql+psycopg://waysklad:change-me@..."
    # и "dev-secret-change-me" тихо работали и без .env, включая в проде при
    # забытой настройке (см. main.py — раньше был отдельный guard только на
    # secret_key, DATABASE_URL мог утечь дефолтным паролем незамеченным).
    # Теперь приложение просто не стартует без .env — Settings() кидает
    # pydantic.ValidationError на первом импорте app.main, а не работает
    # молча с чужим для прода паролем/секретом.
    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 60 * 24 * 30
    debug: bool = False
    telegram_bot_token: str = ""
    # username бота витрины без "@" (например waysklad_shop_bot) — нужен backend,
    # чтобы собрать полную deep-link ссылку t.me/<username>?start=... для входа
    # покупателя (см. app/application/customers/request_login_link.py). Пусто
    # (дефолт) — вход по Telegram недоступен (DomainError при попытке).
    telegram_bot_username: str = ""
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
    # Обязателен (без дефолта на None/in-memory) — кеш read-моделей (витрина,
    # общий каталог платформы) всегда через Redis, во всех окружениях, иначе
    # приложение не стартует (deps/cache.py). Задаётся в .env как
    # redis://redis:6379/2 (тот же Redis, что и остальные, третья БД).
    cache_redis_url: str | None = None
    # Базовый публичный адрес backend (например https://waysklad.ru) — нужен
    # боту витрины, чтобы отправить абсолютный URL фото товара (Product.photo
    # хранится как относительный /uploads/... путь, Telegram sendPhoto по URL
    # требует абсолютный адрес). Пустая строка (дефолт, пока нет прод-домена) —
    # бот показывает карточку товара без фото, а не падает.
    public_base_url: str = ""
    # Логин/bcrypt-хеш пароля для POST /api/admin/login — единственная платформенная
    # учётная запись (не User внутри tenant, в проекте нет понятия "владелец
    # платформы"). Пусто (дефолт) — admin-роутер отключён (см. deps/admin.py).
    # Хеш сгенерировать: python -c "from app.infrastructure.security import hash_password;
    # print(hash_password('...'))"
    admin_login: str = ""
    admin_password_hash: str = ""
    # Срок жизни admin-токена короче обычного (access_token_expire_minutes) —
    # привилегированный доступ ко всей платформе, риск от утечки выше.
    admin_token_expire_minutes: int = 120
    # Белый список origin для CORS, через запятую (например
    # "https://waysklad.gwensoft.ru,https://waysklad.ru"). Пусто (дефолт) —
    # CORSMiddleware не подключается вовсе: свой фронт всегда ходит на тот же
    # origin (см. frontend/nginx.conf в проде, Vite proxy в dev) и в CORS не
    # нуждается. Заполнять только при реальной необходимости у стороннего
    # origin достучаться до API напрямую из браузера — никогда не "*" в проде.
    cors_origins: str = ""
    # Маркетплейс (общая витрина всех магазинов платформы: /api/marketplace/*,
    # межмагазинный блок «похожие товары в других магазинах») выключен по
    # умолчанию — продукт сейчас продаётся как отдельная витрина магазина
    # (/store/<slug>), а не как общая площадка. Выключенный флаг = роутер не
    # подключается вовсе (app/__init__.py), FastAPI отдаёт обычный 404; код
    # use-case'ов и репозиториев остаётся на месте, возврат — одна переменная
    # MARKETPLACE_ENABLED=true в .env.
    marketplace_enabled: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
