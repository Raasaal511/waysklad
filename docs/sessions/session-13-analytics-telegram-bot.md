# Сессия 13 — Аналитика и Telegram-бот

**Дата:** 2026-08-05
**Этап плана:** неделя 9 (README п. 8) — «Аналитика (killer-фича №2)»

## Контекст
Разведка показала, что `presentation/analytics/` и `application/analytics/`
существовали как пустые заготовки-файлы (только докстринги-TODO) — структура
уже была продумана заранее, реализации не было вообще.

Найдена блокирующая проблема: колонка `sale_lines.purchase_price` (снимок
закупочной цены на момент продажи, нужен для расчёта прибыли) существовала в
БД с сессии 03, но никогда не заполнялась — `CreateSaleUseCase` строил
`SaleLine` без неё, маппер писал в БД константу по умолчанию `0`. Без этого
любой отчёт о прибыли был бы в принципе неверным (посчитал бы прибыль как
полную выручку). Это не техдолг, а блокирующий баг сценария (правило 4 из
NEXT_STAGES_PROMPT.md) — исправлено первым делом, до написания аналитики.

## Что сделано
- **Снимок закупочной цены** (`domain/sales/entities.py`,
  `application/sales/create_sale.py`, `infrastructure/db/mappers/sales.py`):
  `SaleLine.purchase_price` + `SaleLine.profit`; `CreateSaleUseCase` берёт
  `product.purchase_price` в момент продажи; маппер читает/пишет колонку,
  которая раньше игнорировалась.
- **domain/analytics/**: `IAnalyticsRepository` (протокол, read-only агрегаты)
  — `totals_for_period`, `top_products`, `profit_by_category`, `dead_stock`,
  `stock_value`, `debts_issued_total`; `render_daily_summary()` для текста
  сводки бота.
- **infrastructure/db/repositories/analytics.py**: `SqlAlchemyAnalyticsRepository`
  — прямые SQL-агрегаты (`GROUP BY`, `func.sum/max/count`) по join
  `sale_lines→sales→products→categories` и `stock_items→products`, без
  построения полных domain-объектов через мапперы (в духе анти-оверинжиниринга
  — обычный SQL, не OLAP). Подключён в `SqlAlchemyUnitOfWork` как `uow.analytics`.
- **application/analytics/**: `GetDashboardUseCase` (сегодня/неделя/месяц),
  `GetTopProductsUseCase`, `GetCategoryProfitUseCase`, `GetDeadStockUseCase`
  (порог 60 дней по умолчанию), `GetStockValueUseCase` — все под
  `require(actor, Permission.ANALYTICS_VIEW)` (право существовало с сессии 02,
  ни разу не применялось в коде до этой сессии).
- **presentation/analytics/**: `GET /dashboard`, `/top-products`,
  `/category-profit`, `/dead-stock`, `/stock-value` — router-level
  `require_permission(ANALYTICS_VIEW)`, схемы через `Money.of(...)` (без этого
  JSON отдавал бы `400.00000` вместо `400.00` — агрегаты из SQL не проходят
  квантование `Money`, в отличие от обычных денежных полей).
- **Telegram-бот** (`infrastructure/telegram.py`): `send_daily_summaries()`
  реализован — обходит все `tenants` через новый `ITenantRepository.list_all()`,
  для каждого с заполненным `owner_telegram_chat_id` собирает сводку
  (продажи/выручка/прибыль/выдано в долг за сегодня) и шлёт через
  `TelegramNotifier.send()`. Точка входа синхронная (`asyncio.run`), сам скрипт
  асинхронный — по докстрингу файла запускается `docker compose exec backend
  python -m app.infrastructure.telegram` из cron на хосте, без celery/redis.
  `Tenant` (domain-сущность) и `TenantMapper` дополнены полем
  `owner_telegram_chat_id` (раньше было только в ORM-модели, в домен не
  прокидывалось).
- **Побочные добавления в существующие интерфейсы**: `ITenantRepository.list_all()`.

## Проверено
93 теста (было 88): снимок закупочной цены не ломает существующие продажи;
`GetDashboardUseCase` считает продажи/выручку/прибыль верно и отклоняет доступ
без `ANALYTICS_VIEW`; топ товаров сортируется по количеству, прибыль по
категориям группируется (в т.ч. товары без категории — в одну группу);
мёртвый остаток отличает никогда не продававшийся товар от только что
проданного; деньги в товаре считаются по остатку после продажи; API-тест на
полный цикл аналитики + 403 для продавца; тест бота — сборка и отправка
сводки с мокнутым `TelegramNotifier`, включая пропуск тенантов без chat_id.
Живой `uvicorn` + реальная `waysklad_dev`: все 5 эндпоинтов аналитики
проверены end-to-end с реальными данными. `compileall` — чисто.

Также по ходу починил разъезжание файла из-за конкурентной правки IDE
(докстринг `infrastructure/telegram.py` был перемещён с уровня модуля внутрь
класса `TelegramNotifier`) — вернул на место, без изменения логики.

## Сверка с README
Чек-лист недели 9 (дашборд, топ товаров, мёртвый остаток, прибыльность по
категориям, деньги в товаре, ежедневная Telegram-сводка) закрыт полностью.
Технического долга не заведено — снимок закупочной цены был блокирующим багом,
почему исправлен в этой же сессии, а не отложен.

Не реализовано (сознательно вне периметра недели 9, за рамками README-чек-листа):
use case «подключить Telegram» (владелец сам вводит `owner_telegram_chat_id`
через бота `/start`) — сейчас это поле можно выставить только напрямую в БД.
Без этого сводка технически не может дойти ни до одного реального магазина.
Это нужно будет сделать до пилота (неделя 12) — стоит явно учесть в неделе 10
или 11, когда будет ясность по регистрации бота в BotFather.

## Дальше
Неделя 10 (README): PWA + офлайн-режим + полировка. Со стороны backend это
в первую очередь синхронизация офлайн-очереди (`client_op_id` на `SaleModel`
уже существует — идемпотентность заложена с сессии 01, но самого
sync-эндпоинта ещё нет, `presentation/sync/router.py` пустой). Также — первый
плановый проход по TECH_DEBT.md (сейчас реестр пуст).
