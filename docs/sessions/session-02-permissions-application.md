# Сессия 02 — Права по ролям + application-слой

**Дата:** 2026-08-04
**Этап плана:** недели 1–2 (роли/права) + заготовка недель 3–8 (use cases)

## Права (`domain/identity/permissions.py`)

`Permission` (21 право вида `products.manage`, `stock.receive`, `analytics.view`…),
матрица `ROLE_PERMISSIONS`, `Actor(id, role)` и `require(actor, permission)` —
проверка первой строкой каждого use case.

| Роль | Может | Не может |
|---|---|---|
| owner | всё | — |
| manager | продавец + кладовщик + товары, склады, сотрудники | прибыль (analytics), журнал (audit); создавать owner/manager |
| seller | продажи, возвраты, долги, заказы, клиенты | закупочные цены, товары, приёмки |
| storekeeper | приёмка, списание, перемещение, инвентаризация, поставщики; видит закупочные цены | продажи, долги |
| analyst | только чтение: товары+закупочные, остатки, долги, заказы, аналитика, журнал | любые изменения |

Тест `test_analyst_is_read_only` держит инвариант «у аналитика только `*.view`».

## Порты
- `IPasswordHasher` (`domain/identity/ports.py`) ← `BcryptPasswordHasher` (infrastructure)
- `IUnitOfWork` типизирован атрибутами всех 11 репозиториев (автодополнение в use case'ах)
- В интерфейсы добавлен `save()`: `IProductRepository` (обновление + синк вариантов),
  `IDebtRepository` (дописывает погашения, заменяет график), `IOrderRepository` (статус и поля)

## Use cases (все с проверкой прав через Actor)

- **auth**: `RegisterShopUseCase` (tenant + владелец + «Основной склад» + посев единиц),
  `LoginUseCase` (одно сообщение об ошибке — не раскрываем, что именно неверно),
  `CreateEmployeeUseCase` (manager не может создать owner/manager — защита от повышения прав)
- **products**: create / update (единица пока из предустановленных, свои — сессия 02 роадмапа)
- **inventory**: receive_goods, write_off, transfer, stocktake (+ акт расхождений
  `StocktakeResult.discrepancies`); общее в `common.py`; списание в минус запрещено
- **sales**: `CreateSaleUseCase` — полный сценарий: списание остатка (ошибка с именем товара
  при нехватке), при «в долг» — проверка лимита клиента и создание долга со ссылкой на
  продажу, расчёт сдачи (`cash_received` → `change`)
- **debts**: issue_debt («запиши на меня», лимит), repay_debt, create_installment
  (сумма графика должна совпасть с остатком долга)
- **orders**: create_order (заказ из переписки, `to_pay` = сумма − предоплата),
  change_status (домен проверяет переходы)
- **counterparties**: create_client, create_supplier

Остались заглушками (по роадмапу): return_sale (сессия 03), import_excel (сессия 02),
analytics (сессия 06), sync (сессия 07).

## Проверено
21 тест: 6 юнит (матрица прав) + 7 интеграционных репозиториев + 8 сквозных use case:
регистрация→логин→неверный пароль, дубль телефона, эскалация прав менеджера,
продавец не создаёт товар, продажа в долг (остаток ↓, долг создан, лимит превышен →
отказ, погашение), нехватка остатка, расчёт сдачи, жизненный цикл заказа с запретом
недопустимого перехода.

## Дальше
- Presentation: эндпоинты auth (register/login) + JWT, роутеры категорий поверх use cases
- Excel-импорт и свои единицы измерения (роадмап недели 3–4)
- Журнал действий (audit) в use case'ах
