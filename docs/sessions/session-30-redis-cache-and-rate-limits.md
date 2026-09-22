# Сессия 30 — Redis-кеш для витрины/маркетплейса, пересмотр rate limit

**Дата:** 2026-09-10
**Этап плана:** пилотные доработки (backend-only)

## Контекст

Пользователь попросил кеширование часто запрашиваемых read-эндпоинтов через
Redis, с явным условием: приложение не должно зависеть только от Redis
(SOLID, паттерн проекта — абстракция + инфраструктурная реализация, как
`INotifier`/`SqlAlchemyUnitOfWork`). Второй заход в том же диалоге — не
упёрся ли активный клиент витрины/маркетплейса в rate limit, настроить лимиты
по факту реальной нагрузки.

## Что сделано

### Кеш

- `app/domain/common/cache.py` — порт `ICache` (Protocol: `get`/`set` с TTL),
  по образцу `INotifier`.
- `app/infrastructure/cache.py` — две реализации: `RedisCache`
  (`redis.asyncio`, лениво импортируется) и `InMemoryCache` (словарь в
  памяти процесса). Обе — graceful degradation: ошибка Redis логируется и
  трактуется как промах кеша, не исключение. Паттерн скопирован с
  `ws_broadcast.py::Broadcaster`.
- `app/infrastructure/cache_aside.py` — хелпер `cached()`/`cache_key()`:
  read-through с pickle-сериализацией результата, общий для всех
  закешированных use case'ов.
- `app/presentation/deps/cache.py` — `CacheDep`, выбор реализации по
  `CACHE_REDIS_URL` (тот же паттерн, что `notifications_redis_url`).
  `Settings.cache_redis_url: str | None = None` — по умолчанию in-memory.
- Закешированы (TTL 20 сек, без событийной инвалидации — см. компромисс
  ниже): `GetStorefrontCatalogUseCase`, `ListMarketplaceProductsUseCase`,
  `GetStorefrontProductUseCase`. Все три — публичные (без авторизации),
  read-heavy, с несколькими запросами к БД на вызов. Конструктор принимает
  `cache: ICache | None = None` — use case работает и без кеша (так
  используется в `telegram_bot/handlers/*`, где cache не передаётся).
- **Не закешировано осознанно**: `GetStorefrontRequestStatusUseCase`
  (покупатель намеренно опрашивает изменение статуса заявки) и чтение чата
  `ListStorefrontMessagesUseCase` — кеш испортил бы реал-тайм UX.
- `docker-compose.prod.yml` — `CACHE_REDIS_URL: redis://redis:6379/2`
  (тот же Redis, третья логическая БД, после rate limit `/0` и notifications
  `/1`).

### Rate limit

Читающие эндпоинты витрины/маркетплейса теперь ещё и закешированы — подняты
заметно щедрее. Пишущие — чуть мягче, но строже, чем чтение:

| Эндпоинт | Было | Стало |
|---|---|---|
| `GET /storefront/{slug}` (каталог) | 60/min | 300/min |
| `GET /storefront/{slug}/products/{id}` | 60/min | 300/min |
| `GET /storefront/requests/status` | 60/min | 300/min |
| `GET /storefront/requests/chat` | 60/min | 300/min |
| `GET /marketplace/products` | 60/min | 300/min |
| `POST /storefront/{slug}/requests` | 20/hour | 40/hour |
| `POST /storefront/requests/chat` | 60/min | 120/min |
| `POST /auth/login` | 10/min | 20/min |
| `POST /auth/register` | 10/hour | без изменений |

Причина: несколько покупателей/сотрудников часто сидят за одним внешним IP
(офис, мобильный оператор с CGNAT), листание витрины с фильтрами шлёт запрос
на каждый клик — старые лимиты были рассчитаны без учёта кеша и общих IP.
`register` не трогали — редкое действие, лимит существует как защита от
спама, не мешает активной работе уже существующего клиента.

## Найдено и исправлено по ходу

Глобальный singleton-кеш (`_cache` в `deps/cache.py`) не был переопределён в
`tests/conftest.py::client` — в отличие от `get_session_factory`/
`get_notifier`, каждый тест получал общий на весь прогон `InMemoryCache`.
Результат: `test_marketplace_excludes_shop_with_storefront_disabled` и
`test_marketplace_no_shops_returns_empty` падали, читая закешированный ответ
предыдущего теста с другой БД. Исправлено: `dependency_overrides[get_cache]
= lambda: InMemoryCache()` — свежий кеш на тест, тот же паттерн, что у
остальных переопределяемых зависимостей.

## Компромисс по инвалидации (осознанный, не будет исправляться без запроса)

Витрина/маркетплейс меняются много где (продажи, приём, списание,
перемещение, изменение товара/склада) — точная инвалидация по событиям
потребовала бы обвязки в 6+ use case'ах. Пользователь явно выбрал короткий
TTL без инвалидации: до 20 секунд устаревания каталога — не критично,
промах кеша это обычный пересчёт, а не ошибка. Если в проде понадобится
инвалидация точнее — обсуждать отдельно, не менять по умолчанию.

## Проверено

259/259 тестов бэкенда (полный прогон, не только затронутые модули).
Импорты новых модулей проверены отдельно (`InMemoryCache`, `RedisCache`,
`CacheDep` создаются без ошибки и без установленного `redis-server`).

## Что дальше

Изменения не закоммичены — рабочая копия оставлена как есть, коммит по
запросу пользователя. Кандидат на будущую сессию: если появится реальная
нагрузка на проде, замерить фактический hit rate кеша (сейчас не
инструментировано — ни счётчиков, ни логов промахов/попаданий).
