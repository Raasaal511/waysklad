# Сессия 01 — Схема БД (часть 1: модели и первая миграция; часть 2: репозитории)

**Дата:** 2026-08-04
**Этап плана:** недели 1–2
**Статус сессии:** в работе — модели и репозитории готовы, авторизация впереди

## Что сделано

### Роли (5 шт.)
`Role(StrEnum)` в `domain/identity/entities.py`; в БД — VARCHAR + CHECK (не нативный PG-enum,
чтобы добавление роли было простой миграцией):

| Роль | Права (базово, уточняются в use case'ах) |
|---|---|
| `owner` | всё, включая закупочные цены и прибыль |
| `manager` | товары, приёмки, заказы, продавцы; без отчётов о прибыли |
| `seller` | продажи, остатки; не видит закупочные цены |
| `storekeeper` | приёмка, списание, перемещение, инвентаризация |
| `analyst` | отчёты и журналы, только чтение |

### ORM-модели — 22 таблицы (`infrastructure/db/models/`)
- **identity** — tenants (+ `owner_telegram_chat_id` для сводок бота), warehouses, users (логин по телефону)
- **catalog** — units (предустановленные сеются при регистрации), categories (вложенность), products, product_variants (размер/цвет)
- **counterparties** — clients (лимит долга), suppliers
- **inventory** — stock_items (остатки; уникальность через два частичных индекса из-за NULL-варианта), stock_documents + lines (приёмка/списание/перемещение/инвентаризация)
- **sales** — sales + sale_lines, sale_returns + lines
- **debts** — debts, debt_repayments, debt_installments (график рассрочки)
- **orders** — orders + order_lines (статусы: new → in_progress → ready → issued)
- **audit** — audit_log (JSONB details)

### Решения, зашитые в схему
- `tenant_id` через `TenantMixin` в каждой таблице — мультиарендность
- `sale_lines.purchase_price` — снимок закупочной цены на момент продажи (иначе прибыль
  считается неверно после изменения цен)
- `sales.client_op_id` (unique per tenant) — идемпотентность офлайн-очереди с недели 10
- `sales.total` — снимок суммы чека для быстрой аналитики
- Документные номера (`number`) — сквозные в пределах магазина
- Enum-колонки (роль, тип документа, способ оплаты, статус заказа) — VARCHAR + CHECK

### Async-стек (по требованию)
Проект пишем асинхронно: `create_async_engine` + `async_sessionmaker` (psycopg3 async),
async `UnitOfWork` (`__aenter__`/`__aexit__`), все порты репозиториев — `async def`,
async-шаблон alembic. В requirements добавлен `greenlet`.

### Миграции
- Папка переименована в `backend/migrations/` (script_location обновлён в alembic.ini)
- Первая миграция: `migrations/versions/2026-08-04_initial_schema.py`

## Проверено
- `configure_mappers()` — маппинг собирается, 22 таблицы
- `alembic upgrade head` применён на локальной БД `waysklad_dev` (postgres@localhost) — 23 таблицы (с alembic_version)
- `pytest` — 1 passed

## Примечания окружения
- Docker Hub не отдавал образ postgres (обрывы сети) — миграция проверена на локальном
  PostgreSQL (Postgres.app), БД `waysklad_dev`, креды postgres/postgres
- Создан `.env` из `.env.example`

## Часть 2 — репозитории (2026-08-04)

### Конвенция
Интерфейсы в domain с префиксом `I` (IProductRepository, IUnitOfWork, INotifier),
реализации в infrastructure без префикса (SqlAlchemyProductRepository, TelegramNotifier).

### Мапперы (`infrastructure/db/mappers/`)
Весь маппинг ORM ↔ домен вынесен в классы-мапперы со статическими методами:
`XxxMapper.to_orm(entity, tenant_id, ...)` и `XxxMapper.to_entity(model, ...)`.
Файл на категорию: identity, catalog, counterparties, inventory, sales, debts, orders.
Контекстные параметры передаются явно: `tenant_id` и `number` — в to_orm,
словари единиц измерения (`units`, `units_by_product`) — в to_entity.
Репозитории делают только запросы + обратную запись id после flush.

### Реализовано (`infrastructure/db/repositories/`)
- `base.py` — SqlAlchemyRepository: сессия и tenant_id из UnitOfWork (лениво, поэтому
  регистрация может выставить tenant после создания); `_next_number()` — сквозные номера
  документов; `_units_map()` / `_product_unit_by_id()` — восстановление Quantity
- `identity.py` — Tenant (add + посев предустановленных единиц), User (get_by_phone без
  фильтра tenant — для логина), Warehouse
- `catalog.py` — Product: add/get/search (ILIKE по имени и артикулу)/get_by_barcode
  (ищет и по штрихкоду варианта)
- `counterparties.py` — Client, Supplier
- `inventory.py` — Stock: change() с row-level lock (SELECT FOR UPDATE — два продавца
  не спишут один остаток дважды), StockDocument
- `sales.py`, `debts.py`, `orders.py` — add/get/списки по интерфейсам
- UnitOfWork собирает все 11 репозиториев; `tenant_id=None` допустим только для регистрации

### Домен: одно дополнение
`User.tenant_id` — identity единственный контекст, знающий о магазине (без этого логин
не может определить, куда входит пользователь).

### Важный фикс: локаль БД
На БД с локалью C `lower()`/ILIKE не работают с кириллицей — поиск «плать» не находил
«Платье». Лечится ICU-локалью при создании БД:
- в docker-compose (оба): `POSTGRES_INITDB_ARGS: "--locale-provider=icu --icu-locale=und"`
- локальные БД пересозданы: `CREATE DATABASE ... TEMPLATE template0 LOCALE_PROVIDER icu ICU_LOCALE 'und' LOCALE 'C'`
- ⚠️ если dev-volume постгреса уже существовал, его надо удалить (`docker compose down -v`),
  иначе initdb-аргументы не применятся

### Проверено
7 тестов (`tests/test_repositories.py`, интеграционные на локальном PostgreSQL,
БД waysklad_test): регистрация магазина с посевом единиц + логин по телефону,
раундтрип товара с вариантами и поиском по штрихкоду варианта, накопление остатка,
изоляция tenant'ов, раундтрип продажи, долг с графиком рассрочки. Всё зелёное.
Добавлены `pytest-asyncio`, `pytest.ini` (asyncio_mode=auto).

## Дальше (часть 3 сессии 01)
- Use cases: регистрация магазина (tenant + владелец + склад), логин, JWT
- Эндпоинты `/api/auth/register`, `/api/auth/login`
- Тест: регистрация → логин → защищённый эндпоинт
