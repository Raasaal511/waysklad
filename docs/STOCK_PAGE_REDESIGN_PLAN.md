# План: редизайн страницы склада (WarehouseDetailPage)

Зафиксировано перед реализацией по запросу пользователя. Три независимые задачи.

**Статус: реализовано.** Отличия от плана при реализации:
- Эндпоинт `restock-recommendations` вынесен в `/inventory`, а не `/analytics` —
  весь роутер `/analytics` защищён `require_permission(ANALYTICS_VIEW)`, которого
  нет у кладовщика/продавца, а им эта рекомендация тоже нужна на своей странице
  склада. Право внутри юзкейса — `Permission.STOCK_VIEW` (есть у всех ролей) +
  `require_warehouse` при явном `warehouse_id`, чтобы не утёк чужой склад.
- Быстрый переход реализован как `Link` на `/products?open=<id>` +
  `useSearchParams` в `ProductsPage.tsx`, подгружает `listAllProducts()` и открывает
  `ProductDetailCard`, затем чистит query-параметр.
- Кнопка «Дозаказать» передаёт `initialProductId` в `MovementForm` (не список строк —
  один товар, форма сама вызывает существующий `addLine`).

## 1. Таблица остатков склада — привести к стилю Товаров/Продаж

Сейчас (`WarehouseDetailPage.tsx`) — голая HTML-таблица «Товар / Остаток»,
визуально выбивается из остального проекта.

Меняем на `product-grid`/`product-tile` (тот же паттерн, что в `ProductsPage.tsx`):
фото, название, остаток с индикатором низкого/нулевого остатка
(`isLowStock`/`isOutOfStock`, `StockWarningIcon`), без цены (тут это остатки
конкретного склада, не карточка товара).

## 2. Блок рекомендаций «стоит дозаказать»

Товар считается кандидатом на дозаказ, если одновременно:
- остаток на этом складе ≤ `min_stock`;
- по товару были продажи за последние 30 дней (значит не мёртвый сток,
  а реально раскупаемый).

Сортировка — по количеству проданного за 30 дней (сначала самые ходовые).

### Backend
- Новый метод `IAnalyticsRepository.restock_recommendations(warehouse_ids, sale_period_days=30) -> list[RestockRecommendation]`.
  `RestockRecommendation`: `product_id, product_name, quantity (текущий остаток), min_stock, quantity_sold_30d`.
- Реализация в `SqlAlchemyAnalyticsRepository` — join остатков (`StockItemModel`,
  фильтр по `warehouse_ids` как в `dead_stock`/`stock_value`) с суммой продаж
  за 30 дней (как в `top_products`), `HAVING quantity <= min_stock AND quantity_sold_30d > 0`.
- Use case `GetRestockRecommendationsUseCase` (`Permission.ANALYTICS_VIEW` — тот же,
  что у dead_stock/top_products; либо ослабить до складского персонала —
  решить при реализации, т.к. кладовщику это тоже нужно видеть).
- Эндпоинт `GET /analytics/restock-recommendations?warehouse_id=` (склад опционален —
  на странице конкретного склада всегда передаём `warehouse_id`).

### Frontend
- `entities/analytics/api.ts` — `getRestockRecommendations(warehouseId)`.
- На `WarehouseDetailPage.tsx` — второй блок карточек под основной таблицей остатков:
  «Стоит дозаказать» с товаром, текущим остатком и продано за 30 дней.
  Каждая карточка — кнопка «Приёмка» сразу открывает `MovementForm` (mode=receive)
  с этим товаром, уже добавленным строкой в корзину (см. п.3).

## 3. Быстрые переходы

- Клик по товару (в таблице остатков и в блоке рекомендаций) → карточка товара
  в разделе «Товары» (переиспользуем `ProductDetailCard`/навигацию туда,
  либо прямой `Link` на `/products?open=<id>` — уточнить механизм открытия
  карточки товара по id при реализации, т.к. `ProductsPage` сейчас открывает
  карточку только по клику из списка, без поддержки query-параметра).
- Кнопка «Дозаказать» в блоке рекомендаций → модалка Приёмки с предзаполненной
  строкой (нужно расширить `MovementForm`/`WarehouseDetailPage`, чтобы принимать
  необязательный `initialLines` при открытии).

## Порядок реализации

1. Backend: аналитика восстановления (метод репозитория, юзкейс, эндпоинт, тест).
2. Frontend: `entities/analytics/api.ts`.
3. Frontend: редизайн таблицы остатков под `product-grid`/`product-tile`.
4. Frontend: блок рекомендаций на `WarehouseDetailPage`.
5. Frontend: быстрый переход клик по товару → карточка в Товарах.
6. Frontend: кнопка «Дозаказать» → предзаполненная Приёмка.
7. Проверка: backend pytest, tsc, vite build, ручная проверка в Docker.
