import os
import random
from typing import AsyncIterator, Callable

# до импорта app.main — тесты логинятся многократно в одном сценарии,
# и лимит /auth/login иначе рвёт их посреди прогона
os.environ["RATE_LIMIT_ENABLED"] = "false"
# тестовое окружение намеренно не хранит секретов
os.environ["DEBUG"] = "true"
os.environ.setdefault("SECRET_KEY", "test-secret-not-for-prod")
# реальные тесты подключаются к своей БД через _ADMIN_DB_URL/db_session_factory
# ниже (CREATE DATABASE per xdist worker) — этот DATABASE_URL используется
# только на уровне модуля, при импорте app.main -> db/session.py, где
# create_async_engine() лениво валидирует URL, но не подключается сразу.
# Settings() теперь требует DATABASE_URL/SECRET_KEY без дефолта (см.
# app/infrastructure/config.py) — без этой строки импорт app.main упал бы.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/waysklad_test"
)
# CACHE_REDIS_URL обязателен (deps/cache.py падает при старте без него) —
# локальный Redis, отдельная логическая БД, чтобы не пересекаться с dev/prod.
# PYTEST_XDIST_WORKER на этом этапе (импорт conftest.py, до pytest_configure)
# у xdist ещё не проставлена во всех воркерах одинаково — вычислять по ней
# DB здесь бессмысленно, все воркеры получили бы один и тот же дефолт. Под
# xdist DB выбирается позже, лениво, в фикстуре client (см. ниже).
os.environ.setdefault("CACHE_REDIS_URL", "redis://localhost:6379/15")
# вход и регистрация покупателя завязаны на Telegram-бота — без username бота
# use-case отказывает ещё до обращения к БД (см. request_login_link.py)
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "waysklad_test_bot")
# фиксированные логин/пароль — тесты admin-роутера логинятся через POST /api/admin/login.
# Присваиваем, а не setdefault: docker compose exec подтягивает .env с прод-хешом,
# и setdefault его не перебивает → все admin-тесты падают «Неверный логин или пароль».
os.environ["ADMIN_LOGIN"] = "test-admin"
# bcrypt с прод-фактором 12 стоит ~0.17s на хеш и ~0.19s на проверку. Фикстуры
# owner_headers/registered_shop регистрируют магазин в сотнях тестов, и эта
# цена, умноженная на число тестов, была основной статьёй времени прогона.
# Криптостойкость здесь ничего не защищает — БД живёт один тест.
os.environ.setdefault("BCRYPT_ROUNDS", "4")
# Маркетплейс выключен в проде (MARKETPLACE_ENABLED=false по умолчанию, см.
# app/infrastructure/config.py), но его код жив и покрыт тестами — включаем
# флаг здесь, до импорта app.main, иначе роутер просто не подключится.
# Поведение при выключенном флаге проверяет test_marketplace_disabled.py,
# который поднимает отдельное приложение.
os.environ["MARKETPLACE_ENABLED"] = "true"
os.environ["ADMIN_PASSWORD_HASH"] = (
    # фактор 4 в тон BCRYPT_ROUNDS выше — проверка пароля с фактором 12 стоила
    # бы 0.19s в каждом тесте admin-роутера
    "$2b$04$Jrj4Ec92zrIx8po/D/s6kelfq8aBBpOfXMwyaG2Fti0TCbJ5Nqra6"  # "test-admin-password"
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.infrastructure.db.models  # noqa: F401  (регистрация всех таблиц)
from app.application.auth.register_shop import RegisterShopCommand, RegisterShopUseCase
from app.domain.catalog.entities import Product
from app.domain.common.money import Money
from app.domain.common.quantity import UNITS
from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer
from app.domain.identity.entities import Role, Tenant, User, Warehouse
from app.domain.identity.permissions import Actor
from app.domain.platform.category_synonyms import SEED_PLATFORM_CATEGORIES
from app.infrastructure.db.models.base import Base
from app.infrastructure.db.models.catalog import PlatformCategoryModel
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.files import LocalFileStorage
from app.infrastructure.security import BcryptPasswordHasher, create_customer_access_token
from app.main import app as fastapi_app
from app.infrastructure.cache.redis_cache import RedisCache
from app.presentation.deps.cache import get_cache
from app.presentation.deps.notifier import get_notifier
from app.presentation.deps.security import get_file_storage
from app.presentation.deps.uow import get_session_factory

_ADMIN_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
_TEST_DB_HOST = "localhost"
# в docker compose Postgres доступен как хост `db`, а не localhost контейнера
if "@db:" in os.environ.get("DATABASE_URL", ""):
    _ADMIN_DB_URL = "postgresql+psycopg://postgres:postgres@db:5432/postgres"
    _TEST_DB_HOST = "db"


def _worker_db_name() -> str:
    """Своя БД на xdist-воркер (waysklad_test_gw0, ...) — иначе параллельные
    drop_all/create_all на одной схеме гонялись бы друг с другом. Читается
    лениво (внутри фикстуры, не на уровне модуля): на момент импорта
    conftest.py PYTEST_XDIST_WORKER у xdist ещё не проставлена одинаково
    во всех воркерах — см. тот же приём у _worker_redis_url ниже."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "")
    return "waysklad_test" + (f"_{worker}" if worker else "")


@pytest.fixture
def random_phone() -> Callable[[], str]:
    """Фабрика уникальных телефонов (валидный формат для Phone) — новый номер на вызов."""

    def make() -> str:
        return "+79" + "".join(random.choices("0123456789", k=9))

    return make


@pytest.fixture(scope="session")
async def _test_db_ready() -> AsyncIterator[str]:
    """Создаёт БД воркера (CREATE DATABASE не может идти внутри транзакции —
    отдельное autocommit-соединение к postgres); skip, если PostgreSQL недоступен.
    Возвращает имя созданной БД."""
    db_name = _worker_db_name()
    admin_engine = create_async_engine(_ADMIN_DB_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            try:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            except ProgrammingError:
                pass  # уже существует с прошлого прогона
    except (OperationalError, OSError):
        await admin_engine.dispose()
        pytest.skip("локальный PostgreSQL недоступен (waysklad_test)")
    await admin_engine.dispose()
    yield db_name


@pytest.fixture(scope="session")
async def _db_engine(_test_db_ready) -> AsyncIterator:
    """Один движок на сессию воркера, со схемой, созданной один раз.

    Раньше схема пересоздавалась на КАЖДЫЙ тест (drop_all + create_all, 42
    таблицы) — это и было основной статьёй времени прогона, дороже самих
    тестов. Теперь схема создаётся один раз, а изоляцию даёт TRUNCATE в
    db_session_factory: тот же «пустая БД на тест» результат в разы дешевле.

    Схема создаётся из моделей (Base.metadata.create_all), не через Alembic —
    поэтому сид platform_categories, который в проде накатывается сид-миграцией
    (migrations/versions/2026-09-18_platform_categories.py), здесь сеется вручную
    тем же списком (app.domain.platform.category_synonyms.SEED_PLATFORM_CATEGORIES).

    NullPool сохранён: движок теперь живёт всю сессию, а event loop
    pytest-asyncio создаёт на каждый тест — соединение из пула пережило бы
    свой loop и упало бы при повторном использовании. Замер показал, что пул
    здесь экономит меньше секунды на прогоне, так что менять смысла нет."""
    db_url = f"postgresql+psycopg://postgres:postgres@{_TEST_DB_HOST}:5432/{_test_db_ready}"
    engine = create_async_engine(db_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    async with factory() as session:
        for slug, name, sort_order in SEED_PLATFORM_CATEGORIES:
            session.add(PlatformCategoryModel(name=name, slug=slug, sort_order=sort_order))
        await session.commit()
    yield engine
    await engine.dispose()


# platform_categories — справочник, а не данные теста: в проде он приезжает
# сид-миграцией и дальше не меняется, тесты его только читают. Поэтому он
# сеется один раз на сессию (в _db_engine) и переживает очистку между тестами,
# вместо того чтобы вычищаться и пересеваться 12 строками на каждый тест.
_MUTABLE_TABLES = [t for t in Base.metadata.tables if t != PlatformCategoryModel.__tablename__]

# TRUNCATE всех таблиц разом: один оператор дешевле, чем DROP/CREATE схемы, а
# RESTART IDENTITY возвращает последовательности к 1 — тесты, которые ждут
# id=1 у первой созданной записи, продолжают работать как при чистой схеме.
# CASCADE нужен из-за внешних ключей между таблицами.
_TRUNCATE_ALL = text(
    "TRUNCATE " + ", ".join(f'"{table}"' for table in _MUTABLE_TABLES) + " RESTART IDENTITY CASCADE"
)


@pytest.fixture
async def db_session_factory(_db_engine) -> AsyncIterator[async_sessionmaker]:
    """Пустая БД на каждый тест, в БД, выделенной текущему xdist-воркеру."""
    engine = _db_engine
    async with engine.begin() as conn:
        await conn.execute(_TRUNCATE_ALL)
    yield async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def make_uow(db_session_factory) -> Callable[[int | None], SqlAlchemyUnitOfWork]:
    """Фабрика UnitOfWork поверх общей тестовой БД: make_uow(tenant_id)."""

    def make(tenant_id: int | None = None) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(tenant_id, session_factory=db_session_factory)

    return make


@pytest.fixture
def hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


@pytest.fixture
def create_shop(make_uow, random_phone) -> Callable:
    """Заводит tenant + владельца напрямую через репозитории, без бизнес-правил use case —
    для тестов репозиторного слоя, которым не нужна валидация регистрации."""

    async def make(shop_name: str = "Тест-магазин") -> tuple[int, str, int]:
        phone = random_phone()
        async with make_uow() as uow:
            tenant = await uow.tenants.add(Tenant(id=None, name=shop_name))
            uow.tenant_id = tenant.id
            owner = await uow.users.add(
                User(
                    id=None, name="Владелец", phone=Phone(phone),
                    role=Role.OWNER, password_hash="hash",
                )
            )
            await uow.commit()
            return tenant.id, phone, owner.id

    return make


@pytest.fixture
async def registered_shop(make_uow, random_phone, hasher) -> tuple[int, str, Actor]:
    """Магазин, заведённый через RegisterShopUseCase: (tenant_id, phone, Actor-владелец).
    Склад больше не создаётся автоматически при регистрации (владелец заводит его сам
    в онбординге) — тестовый склад заводим здесь явно, чтобы не переписывать все тесты,
    которые полагаются на готовый склад."""
    phone = random_phone()
    result = await RegisterShopUseCase(make_uow(), hasher).execute(
        RegisterShopCommand(
            shop_name="Магазин Беркат",
            owner_name="Ахмед",
            phone=phone,
            password="secret123",
            personal_data_consent=True,
        )
    )
    owner = result.owner
    async with make_uow(owner.tenant_id) as uow:
        await uow.warehouses.add(Warehouse(id=None, name="Основной склад"))
        await uow.commit()
    return owner.tenant_id, phone, Actor(id=owner.id, role=owner.role)


@pytest.fixture
async def warehouse_id(make_uow, registered_shop) -> int:
    """id основного склада, созданного при регистрации магазина."""
    tenant_id, _, _ = registered_shop
    async with make_uow(tenant_id) as uow:
        return (await uow.warehouses.list())[0].id


@pytest.fixture
def create_product(make_uow) -> Callable:
    """Заводит товар напрямую через репозиторий (без проверки прав) — для тестов,
    где создание товара не является предметом проверки."""

    async def make(tenant_id: int, **overrides) -> Product:
        fields = dict(
            id=None,
            name="Товар",
            unit=UNITS["pcs"],
            purchase_price=Money.of("150"),
            retail_price=Money.of("250"),
        )
        fields.update(overrides)
        product = Product(**fields)
        async with make_uow(tenant_id) as uow:
            await uow.products.add(product)
            await uow.commit()
        return product

    return make


def _worker_redis_url() -> str:
    """Своя логическая Redis DB на xdist-воркер (PYTEST_XDIST_WORKER читается
    здесь, лениво — на момент импорта conftest.py xdist её ещё не проставляет
    одинаково во всех воркерах, см. комментарий у CACHE_REDIS_URL выше).
    Без этого конкурентные тесты в разных БД делят один Redis-кеш
    (marketplace_catalog и т.п. в cache_aside.py, admin:error_log) — один
    воркер видит запись/закешированный результат другого."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "").removeprefix("gw")
    db = 15 - (int(worker) % 16) if worker.isdigit() else 15
    # docker compose: Redis как хост `redis`; CI/локально — localhost
    host = "redis" if "://redis:" in os.environ.get("CACHE_REDIS_URL", "") else "localhost"
    return f"redis://{host}:6379/{db}"


@pytest.fixture
async def client(db_session_factory, tmp_path) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент FastAPI-приложения с подменённой тестовой БД и хранилищем файлов."""
    redis_url = _worker_redis_url()

    # свежий RedisCache на тест: соединение привязано к event loop текущего
    # теста (pytest-asyncio создаёт новый loop на каждую функцию), общий
    # на модуль клиент из deps/cache.py пережить это не может — своя DB
    # flushdb'ится тут же, так что кеш предыдущего теста не просачивается
    test_cache = RedisCache(redis_url)
    await test_cache._redis.flushdb()
    fastapi_app.dependency_overrides[get_cache] = lambda: test_cache

    # admin_alerts.error_log — синглтон, созданный при импорте app.main с
    # дефолтной DB (15) до того, как воркер узнал свой номер — переключаем
    # его соединение на ту же DB, что и test_cache выше, на время теста
    from app.infrastructure.observability import admin_alerts

    original_error_log_redis = None
    if admin_alerts.error_log is not None:
        original_error_log_redis = admin_alerts.error_log._redis
        admin_alerts.error_log._redis = test_cache._redis

    fastapi_app.dependency_overrides[get_session_factory] = lambda: db_session_factory
    fastapi_app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(tmp_path)
    fastapi_app.dependency_overrides[get_notifier] = lambda: None  # без реальных HTTP-запросов в Telegram
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    if original_error_log_redis is not None:
        admin_alerts.error_log._redis = original_error_log_redis
    await test_cache._redis.aclose()
    fastapi_app.dependency_overrides.clear()


class SqlQueryCounter:
    """Считает SQL-запросы, выполненные через движок db_session_factory, пока
    активен (см. фикстуру sql_query_counter) — нет готового приёма для этого
    в проекте (см. промпт M-B2 п.2), поэтому используем event.listen на
    Engine.before_cursor_execute, самый низкоуровневый и надёжный хук
    SQLAlchemy (считает буквально то, что ушло на сервер, а не ORM-вызовы)."""

    def __init__(self):
        self.count = 0

    def _on_execute(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1

    def reset(self) -> None:
        self.count = 0


@pytest.fixture
async def sql_query_counter(db_session_factory) -> AsyncIterator[SqlQueryCounter]:
    """counter.count — число SQL-запросов с последнего reset()/начала теста,
    выполненных через тестовую БД (db_session_factory и, следовательно, client —
    оба используют один engine, см. фикстуру client)."""
    from sqlalchemy import event

    engine = db_session_factory.kw["bind"]
    counter = SqlQueryCounter()
    event.listen(engine.sync_engine, "before_cursor_execute", counter._on_execute)
    try:
        yield counter
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", counter._on_execute)


@pytest.fixture
def db_engine_queries(db_session_factory):
    """Считает SQL-запросы за блок — для проверок на N+1.

    Считаются только запросы к данным: BEGIN/COMMIT и прочая служебка
    отфильтрованы, иначе счётчик зависел бы от транзакционных границ.
    """
    from contextlib import contextmanager

    from sqlalchemy import event

    engine = db_session_factory.kw["bind"].sync_engine

    class Counter:
        count = 0

    @contextmanager
    def collect():
        counter = Counter()

        def on_execute(conn, cursor, statement, parameters, context, executemany):
            counter.count += 1

        event.listen(engine, "before_cursor_execute", on_execute)
        try:
            yield counter
        finally:
            event.remove(engine, "before_cursor_execute", on_execute)

    return collect


@pytest.fixture
async def customer_headers(make_uow, random_phone) -> Callable:
    """Authorization-заголовок авторизованного покупателя витрины — заводит
    Customer напрямую через репозиторий (минуя реальный Telegram-флоу входа,
    который не нужен тестировать здесь) и выдаёт обычный JWT.

    Возвращает фабрику (headers, phone), а не готовый dict — каждый вызов
    заводит НОВОГО покупателя (свой телефон), чтобы тесты на антиспам/лимиты
    по телефону не пересекались с другими вызовами внутри теста; phone нужен
    тестам, которые проверяют, что клиент в CRM создался с этим номером."""

    async def make() -> tuple[dict, str]:
        phone = random_phone()
        async with make_uow() as uow:
            customer = await uow.customers.add(Customer(id=None, phone=Phone(phone)))
            await uow.commit()
        token = create_customer_access_token(customer.id)
        return {"Authorization": f"Bearer {token}"}, phone

    return make


@pytest.fixture
async def owner_headers(client, random_phone) -> dict:
    """Authorization-заголовок владельца только что зарегистрированного через API магазина.
    Склад больше не создаётся автоматически при регистрации — заводим его явно тем же
    HTTP-запросом, каким это сделал бы владелец в онбординге."""
    response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Магазин Беркат",
            "owner_name": "Ахмед",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": True,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    warehouse_response = await client.post(
        "/api/inventory/warehouses", headers=headers, json={"name": "Основной склад"}
    )
    assert warehouse_response.status_code == 201, warehouse_response.text
    return headers
