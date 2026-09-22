# Карта роутов ВайСклад API

Все пути даны с общим префиксом `/api` (задаётся один раз в `app/__init__.py`).
Всего роутов: **42**. Дата среза: 2026-08-05.

---

## Auth — `/api/auth` (4)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| POST | `/auth/register` | Регистрация нового магазина (владелец + основной склад) | Публичный |
| POST | `/auth/login` | Вход по телефону/паролю | Публичный |
| POST | `/auth/employees` | Завести сотрудника (продавец/кладовщик/аналитик/управляющий) | `USERS_MANAGE` |
| POST | `/auth/telegram` | Подключить Telegram-чат для ежедневной сводки бота | `SETTINGS_MANAGE` (только владелец) |

## Products — `/api/products` (9)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| POST | `/products` | Создать товар | `PRODUCTS_MANAGE` |
| PUT | `/products/{product_id}` | Обновить товар (в т.ч. варианты) | `PRODUCTS_MANAGE` |
| POST | `/products/{product_id}/photo` | Загрузить фото товара | `PRODUCTS_MANAGE` |
| POST | `/products/import` | Импорт номенклатуры из Excel | `PRODUCTS_MANAGE` |
| POST | `/products/units` | Добавить свою единицу измерения | `PRODUCTS_MANAGE` |
| GET | `/products/units` | Список единиц измерения | — |
| GET | `/products` | Поиск/список товаров (закупочная цена скрыта без права) | `PRODUCTS_VIEW` |
| GET | `/products/barcode/{barcode}` | Найти товар по штрихкоду (скан камерой) | `PRODUCTS_VIEW` |
| GET | `/products/{product_id}` | Карточка товара | `PRODUCTS_VIEW` |

## Inventory — `/api/inventory` (4)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| POST | `/inventory/receive` | Приёмка товара на склад | `STOCK_RECEIVE` |
| POST | `/inventory/write-off` | Списание (порча/усушка) | `STOCK_WRITE_OFF` |
| POST | `/inventory/transfer` | Перемещение между складами | `STOCK_TRANSFER` |
| POST | `/inventory/stocktake` | Инвентаризация с актом расхождений | `STOCK_TAKE` |

## Sales — `/api/sales` (3)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| POST | `/sales` | Быстрая продажа (скидка, способ оплаты, сдача) | `SALES_CREATE` |
| POST | `/sales/{sale_id}/returns` | Возврат по продаже | `SALES_RETURN` |
| GET | `/sales/{sale_id}/receipt` | Текст квитанции + ссылка wa.me | `SALES_CREATE` |

## Sync — `/api/sync` (1)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| POST | `/sync/sales` | Накат офлайн-очереди продаж (идемпотентно по `client_op_id`) | `SALES_CREATE` |

## Debts — `/api/debts` (7)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| POST | `/debts` | Выдать долг клиенту | `DEBTS_MANAGE` |
| POST | `/debts/suppliers` | Выдать долг поставщику («мы должны») | `DEBTS_MANAGE` |
| POST | `/debts/{debt_id}/repayments` | Частичное погашение долга | `DEBTS_MANAGE` |
| POST | `/debts/{debt_id}/installments` | График беспроцентной рассрочки | `DEBTS_MANAGE` |
| GET | `/debts/due` | Долги «должны сегодня» (по умолчанию — сегодня) | `DEBTS_VIEW` |
| GET | `/debts/client/{client_id}` | Баланс + долги клиента | `DEBTS_VIEW` |
| GET | `/debts/supplier/{supplier_id}` | Баланс + долги перед поставщиком | `DEBTS_VIEW` |

## Orders — `/api/orders` (4)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| POST | `/orders` | Создать заказ клиента (состав, предоплата, дата готовности) | `ORDERS_MANAGE` |
| PATCH | `/orders/{order_id}/status` | Сменить статус (новый→в работе→готов→выдан) | `ORDERS_MANAGE` |
| GET | `/orders` | Список активных заказов (без выданных) | `ORDERS_VIEW` |
| GET | `/orders/{order_id}` | Карточка заказа | `ORDERS_VIEW` |

## Counterparties — `/api/counterparties` (4)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| POST | `/counterparties/clients` | Завести клиента | `CLIENTS_MANAGE` |
| GET | `/counterparties/clients` | Поиск клиентов | `CLIENTS_VIEW` |
| POST | `/counterparties/suppliers` | Завести поставщика | `SUPPLIERS_MANAGE` |
| GET | `/counterparties/suppliers` | Список поставщиков | — |

## Analytics — `/api/analytics` (5)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| GET | `/analytics/dashboard` | Выручка/прибыль/число продаж — сегодня/неделя/месяц | `ANALYTICS_VIEW` |
| GET | `/analytics/top-products` | Топ товаров по продажам за период | `ANALYTICS_VIEW` |
| GET | `/analytics/category-profit` | Прибыльность по категориям | `ANALYTICS_VIEW` |
| GET | `/analytics/dead-stock` | Мёртвый остаток (не продаётся 60+ дней) | `ANALYTICS_VIEW` |
| GET | `/analytics/stock-value` | «Деньги в товаре» (остаток × закупочная) | `ANALYTICS_VIEW` |

## Audit — `/api/audit` (1)

| Метод | Путь | Назначение | Доступ |
|---|---|---|---|
| GET | `/audit` | Журнал действий (кто что продал/изменил/удалил) | `AUDIT_VIEW` |

---

## Не реализовано / вне API

- **Аналитика → Telegram**: сама ежедневная сводка не эндпоинт, а cron-скрипт
  (`python -m app.infrastructure.telegram`, запускается вне HTTP через
  `docker compose exec`).
- **Публичная витрина** (README §5.2) — вторая очередь, не начата.
- **Sync** пока принимает только продажи — возвраты/приёмки/списания в
  офлайн-очередь не входят (см. `docs/sessions/TECH_DEBT.md`, пункт #2).
