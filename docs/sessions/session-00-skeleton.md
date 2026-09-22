# Сессия 00 — Каркас проекта

**Дата:** 2026-08-04
**Этап плана:** подготовительный (перед неделями 1–2)

## Что сделано

### Архитектура
Монолит на чистой архитектуре: слои `domain → application → infrastructure → presentation`,
внутри каждого слоя — разбивка по категориям (catalog, inventory, sales, debts, orders…).
Бэкенд: FastAPI + SQLAlchemy 2.0 + PostgreSQL + Alembic. Frontend отложен.

### Инфраструктура
- `docker-compose.yml` — дев-окружение: postgres + backend с hot-reload
- `docker-compose.prod.yml` — прод: + nginx, без reload
- `deploy/nginx.conf`, `deploy/backup.sh` (ежедневный pg_dump по cron)
- `.env.example` — единая точка конфигурации
- Alembic настроен (`backend/alembic/`), миграций пока нет

### Домен (рабочий код, не заглушки)
- `Money` — Decimal, копейки, запрет float
- `Quantity` + предустановленные единицы (шт/кг/мл/м²…), запрет дробного для штучных
- `Sale` — чек: сумма, скидка, сдача; продажа в долг требует клиента
- `Debt` — долговая книга: погашения не больше остатка, график рассрочки
- `Order` — статусы новый → в работе → готов → выдан, контроль переходов
- `StockDocument` — приёмка/списание/перемещение/инвентаризация, остаток меняется только документом
- Порты-репозитории (Protocol) для всех категорий

### Инфраструктурный слой
- `config.py` (pydantic-settings), `security.py` (JWT + bcrypt)
- `SqlAlchemyUnitOfWork` — транзакция + tenant_id
- ORM-модели identity: tenants, warehouses, users (+ `TenantMixin` — мультиарендность)

### Application / Presentation
- Эталонный use case: `application/sales/create_sale.py` — остальные пишутся по образцу
- Заглушки сценариев всех категорий с привязкой к неделям плана
- Роутеры по категориям, собираются в `app/__init__.py`; `deps.py` достаёт user/tenant/role из JWT

## Проверено
- Все файлы компилируются (117 шт.)
- `pytest tests` — 1 passed (`GET /api/health`)

## Как запустить
```bash
cp .env.example .env        # поменять пароли
docker compose up --build
```

## Следующая сессия (01, недели 1–2)
- Спроектировать схему БД по всем категориям (ORM-модели + первая миграция)
- Авторизация: регистрация магазина (tenant + владелец), логин по телефону, JWT
- Репозитории identity, подключение к UnitOfWork
- Тесты на регистрацию/логин/изоляцию tenant'ов
