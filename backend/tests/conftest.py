import os
import random
from typing import AsyncIterator, Callable

# до импорта app.main — тесты логинятся многократно в одном сценарии,
# и лимит /auth/login иначе рвёт их посреди прогона
os.environ["RATE_LIMIT_ENABLED"] = "false"
# тестовое окружение намеренно не хранит секретов — стартовая проверка
# SECRET_KEY (см. app/main.py) иначе не даст приложению импортироваться
os.environ["DEBUG"] = "true"
# CACHE_REDIS_URL обязателен (deps/cache.py падает при старте без него) —
# локальный Redis, отдельная логическая БД, чтобы не пересекаться с dev/prod
os.environ.setdefault("CACHE_REDIS_URL", "redis://localhost:6379/15")
# фиксированные логин/пароль — тесты admin-роутера логинятся через POST /api/admin/login
os.environ.setdefault("ADMIN_LOGIN", "test-admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    "$2b$12$hVd0LRFO6SZp0qzOTV3pAOxTeF0fB18uj/us6lvrgGHJxvaQL4d/W",  # "test-admin-password"
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.infrastructure.db.models  # noqa: F401  (регистрация всех таблиц)
from app.application.auth.register_shop import RegisterShopCommand, RegisterShopUseCase
from app.domain.catalog.entities import Product
from app.domain.common.money import Money
from app.domain.common.quantity import UNITS
from app.domain.common.phone import Phone
from app.domain.identity.entities import Role, Tenant, User, Warehouse
from app.domain.identity.permissions import Actor
from app.infrastructure.db.models.base import Base
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.files import LocalFileStorage
from app.infrastructure.security import BcryptPasswordHasher
from app.main import app as fastapi_app
from app.infrastructure.cache import RedisCache
from app.infrastructure.config import settings
from app.presentation.deps.cache import get_cache
from app.presentation.deps.notifier import get_notifier
from app.presentation.deps.security import get_file_storage
from app.presentation.deps.uow import get_session_factory

TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/waysklad_test"


@pytest.fixture
def random_phone() -> Callable[[], str]:
    """Фабрика уникальных телефонов (валидный формат для Phone) — новый номер на вызов."""

    def make() -> str:
        return "+79" + "".join(random.choices("0123456789", k=9))

    return make


@pytest.fixture
async def db_session_factory() -> AsyncIterator[async_sessionmaker]:
    """Чистая схема waysklad_test на каждый тест; skip, если postgres недоступен."""
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except (OperationalError, OSError):
        await engine.dispose()
        pytest.skip("локальный PostgreSQL недоступен (waysklad_test)")
    yield async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    await engine.dispose()


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
            shop_name="Магазин Беркат", owner_name="Ахмед", phone=phone, password="secret123"
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


@pytest.fixture
async def client(db_session_factory, tmp_path) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент FastAPI-приложения с подменённой тестовой БД и хранилищем файлов."""
    # свежий RedisCache на тест: соединение привязано к event loop текущего
    # теста (pytest-asyncio создаёт новый loop на каждую функцию), общий
    # на модуль клиент из deps/cache.py пережить это не может — тестовая БД
    # 15 flushdb'ится тут же, так что кеш предыдущего теста не просачивается
    test_cache = RedisCache(settings.cache_redis_url)
    await test_cache._redis.flushdb()
    fastapi_app.dependency_overrides[get_cache] = lambda: test_cache

    fastapi_app.dependency_overrides[get_session_factory] = lambda: db_session_factory
    fastapi_app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(tmp_path)
    fastapi_app.dependency_overrides[get_notifier] = lambda: None  # без реальных HTTP-запросов в Telegram
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    await test_cache._redis.aclose()
    fastapi_app.dependency_overrides.clear()


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
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    warehouse_response = await client.post(
        "/api/inventory/warehouses", headers=headers, json={"name": "Основной склад"}
    )
    assert warehouse_response.status_code == 201, warehouse_response.text
    return headers
