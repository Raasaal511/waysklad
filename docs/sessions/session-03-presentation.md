# Сессия 03 — Presentation: deps/, роутеры, JWT

**Дата:** 2026-08-04
**Этап плана:** недели 1–2 (авторизация) + HTTP-слой поверх готовых use case'ов

## deps/ — вся DI-проводка (роуты тонкие)

`presentation/deps/` (вместо deps.py):
- `auth.py` — разбор Bearer-токена: `CurrentUser(id, tenant_id, role)` из JWT,
  `ActorDep` для use case'ов; 401 без токена/с плохим токеном
- `uow.py` — `get_uow` (tenant из JWT), `get_public_uow` (без tenant — регистрация/логин),
  `get_session_factory` — единая точка подмены БД в тестах через dependency_overrides
- `security.py` — `HasherDep` (bcrypt)
- `use_cases.py` — фабрики всех 17 use case'ов; хелпер `_with_uow(cls)` для типовых

Роут = распарсить запрос → вызвать use case → отдать схему. Никакой логики.

## Ошибки → HTTP (`presentation/errors.py`)
`NotFoundError` → 404, `AccessDeniedError` → 403, `DomainError` (включая
`InsufficientStockError`) → 400. Регистрируется в main.py.

## Эндпоинты

| Категория | Маршруты |
|---|---|
| auth | POST /api/auth/register (201 + JWT), /login, /employees |
| products | POST, PUT /{id}, GET ?query=, GET /{id}, GET /barcode/{barcode} |
| inventory | POST /receive, /write-off, /transfer, /stocktake (с актом расхождений) |
| sales | POST /api/sales (сдача в ответе) |
| debts | POST, POST /{id}/repayments, POST /{id}/installments, GET /client/{id} |
| orders | POST, PATCH /{id}/status, GET (активные) |
| counterparties | POST+GET /clients, POST+GET /suppliers |

GET-запросы (чтение) идут через uow напрямую в роуте — CQRS-lite, как договаривались.
Закупочная цена и наценка в ответах видны только ролям с `purchase_prices.view` —
остальным приходит `null` (проверяется тестом: продавец получает null, владелец — цену).

## Проверено
24 теста, из них 3 новых API-теста через HTTP (httpx ASGITransport, БД подменяется
через dependency_overrides): регистрация → логин → неверный пароль → 401 без токена;
полный торговый цикл (товар → приёмка → продажа со сдачей → продажа в долг → долг 750 →
погашение → 400 при нехватке остатка с именем товара); права продавца через API
(403 на создание товара, null вместо закупочной цены).

## Заметка
JWT подписывается SECRET_KEY из .env — для прода нужен ключ 32+ байта
(сейчас dev-значение, pyjwt предупреждает).

## Дополнение: конвенции presentation (введены после ревью)

1. **Роут — не больше 2 строк кода.** Всё, что длиннее — выносится:
   сборка команды → `to_command()` на request-схеме, зависимости → готовые
   алиасы `XxxDep = Annotated[XxxUseCase, Depends(get_xxx)]` в `deps/use_cases.py`.
2. **`__init__.py` против дублей**: общий префикс `/api` задаётся один раз
   в `app/__init__.py`; роутеры категорий — только `/products`, `/sales`…
   `deps/__init__.py` реэкспортирует все зависимости — импорт одной строкой
   `from app.presentation.deps import ActorDep, CreateSaleDep, UowDep`.
3. Внешние URL не изменились (`/api/...`), все 24 теста прошли без правок логики.

## Сверка с README (правило: после каждой работы)
- README п. 5.1 «Товары и склад» — карточка/варианты/остатки/приёмка/списание/
  перемещение/инвентаризация: API готов ✅; скан камерой, импорт Excel, мин. остаток
  с предупреждением — впереди (недели 3–4)
- П. 5.1 «Продажи» — экран продажи/скидка/сдача/пометка оплаты ✅; возвраты и
  квитанция PDF — впереди (сессия по неделям 5–6)
- П. 5.1 «Долги» — долговая книга/рассрочка/частичные погашения ✅; напоминания
  «сегодня должны вернуть» — вместе с ботом (неделя 9)
- П. 5.1 «Заказы» — статусы/предоплата ✅
- П. 5.1 «Команда» — роли ✅ (5 вместо 2 из README — осознанное расширение),
  журнал действий — таблица есть, запись в use case'ах впереди
- Отклонений от README, требующих решения, нет

## Дальше
- Роутеры analytics и sync — заглушки (роадмап недели 9–10)
- Excel-импорт, свои единицы, фото товаров (недели 3–4)
- Журнал действий (audit) в use case'ах и его просмотр владельцем
