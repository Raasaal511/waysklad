# Сессия 28 — Sync: возвраты/приёмки/списания + коды ошибок, видимость Client/Supplier по складу

**Дата:** 2026-09-05
**Этап плана:** плановый разбор `TECH_DEBT.md` (backend-only)

## Контекст

Проход по открытым находкам `TECH_DEBT.md`, закрыто три штуки одним заходом: №2, №3, №5.

## Что сделано

1. **№2 — офлайн-синк только продаж.** `POST /api/sync/sales` (контракт не переименован,
   чтобы не ломать уже написанный клиент) теперь принимает опциональные `returns`/
   `receipts`/`writeoffs` рядом с `sales`. `ReturnSaleCommand`/`ReceiveGoodsCommand`/
   `WriteOffCommand` получили `client_op_id` — та же идемпотентность, что уже была у
   продаж (`SaleReturn`/`StockDocument` получили колонку `client_op_id` +
   `UNIQUE(tenant_id, client_op_id)`, `get_by_client_op_id` в репозиториях).
   `ApplyOfflineSalesUseCase` обрабатывает все 4 списка одним и тем же паттерном —
   каждая операция независима, ошибка одной не блокирует остальные (в том числе
   других типов), `IntegrityError` на повторе резолвится в уже применённую операцию.
2. **№3 — типы ошибок в пачке не различались.** `OfflineOpError`/`OfflineOpErrorResponse`
   получили поле `code` (имя класса исключения — `InsufficientStockError`,
   `AccessDeniedError`, `NotFoundError` и т.п.; `"IntegrityConflict"` для
   нерезолвящегося дубля `client_op_id`) и `op_type` (`sale`/`return`/`receipt`/
   `writeoff` — чтобы фронт понимал, к какому списку относится ошибка, раз все
   ошибки лежат в одном общем списке `errors`). Новых классов исключений не заводили
   — `type(exc).__name__` достаточно фронту для switch без выдуманного enum.
3. **№5 (вторая половина) — Client/Supplier без warehouse-скоупа.** В отличие от
   Order/Debt (сессия 26 — одна операция = один склад, обычная FK-колонка), у
   Client/Supplier нет единственного «своего» склада: один клиент может покупать на
   разных складах одного магазина. Обсудили с пользователем два варианта — подзапрос
   по факту операций на лету (проще, без риска рассинхронизации, но дороже на
   чтение) и связующая many-to-many таблица (быстрее читать, требует не забыть все
   точки записи). Выбрана связующая таблица, по образцу `WarehouseAssignmentModel`:
   - Новые таблицы `warehouse_client_links(warehouse_id, client_id)` /
     `warehouse_supplier_links(warehouse_id, supplier_id)`, без своей `tenant_id`
     колонки — изоляция транзитивна через `warehouse_id`/`client_id` (тот же паттерн,
     что применили к `WarehouseAssignmentModel` при закрытии находки №17).
   - Backfill-миграция заполняет связи из истории: `sales`/`orders`/`debts` →
     `warehouse_client_links`, `stock_documents`/`debts` → `warehouse_supplier_links`.
   - Запись при создании — `IClientRepository.link_to_warehouse`/
     `ISupplierRepository.link_to_warehouse` (upsert, `ON CONFLICT DO NOTHING`),
     вызывается из пяти мест: `CreateSaleUseCase`, `CreateOrderUseCase`,
     `ReceiveGoodsUseCase` (поставщик), `IssueDebtUseCase`, `IssueSupplierDebtUseCase`.
   - `search_clients`/`list_suppliers` (`app/presentation/counterparties/router.py`)
     фильтруют через `EXISTS` по этим таблицам, если актор warehouse-scoped —
     тот же паттерн, что `orders`/`debts` роутеры уже используют для своих списков.
     Карточка одного клиента (`get_client_summary`/`get_client_timeline`) не
     фильтровалась — это точечный лукап по id, не список.

## Найдено по ходу (не в скоупе, заведено отдельным пунктом)

Пользователь по итогам ревью диффа заметил, что `search_clients`/`list_suppliers`
стали единственными раздутыми (4-6 строк с прямым `async with uow`) эндпоинтами в
`counterparties/router.py`, где все остальные — однострочники, делегирующие в use
case. Проверка показала: это не огрех этой сессии, а существующий паттерн всего
проекта — `orders`, `debts`, `products` уже так делают для всех read-only
эндпоинтов (19 мест до этой сессии). Пользователь решил не смешивать это с точечным
техдолгом — заведено как **находка №23→24** в `TECH_DEBT.md` (роутеры без
делегирования в use case для read-only путей), решать отдельной сессией на весь
проект целиком, не точечно.

## Проверено

245/245 тестов бэкенда (3 новых: `test_sync_returns_receipts_writeoffs_via_api`,
`test_sync_error_has_typed_code_via_api`, `test_counterparties_scoped_by_warehouse_via_api`).
Две новые миграции (`2026-09-05_offline_sync_client_op_id.py`,
`2026-09-05_warehouse_counterparty_links.py`) — единственный `alembic heads`, без
ветвления; прогнаны `upgrade head`/`downgrade` на одноразовой Postgres-базе,
backfill проверен вручную на существующих продажах/приёмках.

## Что дальше

Из реестра `TECH_DEBT.md` остаются открытыми/частичными: №2/№3/№5 закрыты этой
сессией; №6 (офлайн-долг — фронтенд не сделан), №7 (формат акта сверки не
определён), №23 (backfill витрины — прогнать на проде перед деплоем) и новая №24
(рефакторинг роутеров — отдельная сессия по явному запросу пользователя).
