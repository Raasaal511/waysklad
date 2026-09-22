# Приватная админ-панель — логин, статус сервера, магазины, лог ошибок

Раздел API, отдельный от обычной авторизации по ролям (owner/manager/...) —
данные не про конкретный магазин, а про всю платформу целиком (список
магазинов, их блокировка, состояние БД/Redis, последние серверные ошибки).
Скрыт от обычных пользователей — роутер не публикует ссылку ни в каком меню,
фронт сам решает, где и кому показывать эту вкладку.

---

## Авторизация — логин/пароль, свой JWT

**`POST /api/admin/login`** (без авторизации, это сама точка входа)

```ts
// запрос
{ login: string, password: string }
// ответ (200)
{ access_token: string, expires_in_minutes: number }  // сейчас 120
```

`401` — неверный логин или пароль (текст ответа одинаковый в обоих случаях,
не палит, что именно неверно). Rate limit `10/hour` на IP.

Все остальные `/api/admin/*` эндпоинты требуют `Authorization: Bearer
<access_token>` из ответа логина — `401`, если заголовка нет или токен
недействителен/истёк. **Это не тот же токен, что у обычных пользователей** —
свой отдельный JWT (`scope: "admin"`), не имеет отношения к User/Role внутри
магазина и не проходит по обычным `/api/*` эндпоинтам, и наоборот.

Срок жизни токена короче обычного — 2 часа, а не 30 дней (админ-доступ
привилегированный, поэтому короче живёт). Держать токен во фронте так же,
как любой другой секрет сессии — не хардкодить, не логировать.

```
POST /api/admin/login          {login, password}       -> {access_token, ...}
GET  /api/admin/status         Authorization: Bearer …
GET  /api/admin/tenants        Authorization: Bearer …
GET  /api/admin/tenants/{id}   Authorization: Bearer …
POST /api/admin/tenants/{id}/suspend    Authorization: Bearer …
POST /api/admin/tenants/{id}/unsuspend  Authorization: Bearer …
GET  /api/admin/error-logs     Authorization: Bearer …
```

---

## `GET /api/admin/status`

```ts
{
  db_connected: boolean,
  redis_connected: boolean,
  active_users: number,       // все активные пользователи, по всей платформе
  active_tenants: number,     // все магазины, по всей платформе
  online_now: number,         // см. предупреждение ниже
  online_now_note: string,    // "только этот воркер, не вся платформа"
}
```

**`online_now` — не точное число онлайн по всей платформе.** Это открытые
WebSocket-соединения (уведомления/чат) только в том backend-процессе
(воркере), который обработал именно этот запрос. В проде backend поднят с
4 воркерами (`--workers 4`), у каждого свой независимый список открытых
сокетов — общего счётчика сейчас нет. Показывать как есть, с оговоркой
(`online_now_note` уже готовая строка для подсказки/тултипа), либо не
показывать вовсе, если это будет вводить в заблуждение.

`db_connected` / `redis_connected` — `false`, если соответствующая проверка
не прошла. Больше никаких метрик деградации (задержка, нагрузка) сейчас нет.

Ответ кешируется на backend 5 секунд (кроме `online_now`, который всегда
живой) — можно опрашивать чаще без опасений, лишний трафик до БД не пойдёт.

---

## `GET /api/admin/tenants` — список магазинов

```ts
{
  tenants: {
    id: number,
    name: string,
    slug: string | null,
    storefront_enabled: boolean,
    is_suspended: boolean,
    created_at: string,   // ISO datetime
  }[]
}
```

Только базовые поля — без счётчиков пользователей/товаров на каждую строку
(дорого при большом числе магазинов). Новые сначала (`created_at desc`).

## `GET /api/admin/tenants/{id}` — карточка одного магазина

```ts
{
  id: number,
  name: string,
  slug: string | null,
  storefront_enabled: boolean,
  is_suspended: boolean,
  created_at: string,
  owner: { name: string, phone: string } | null,  // null — если owner деактивирован
  users_count: number,      // активные пользователи этого магазина
  products_count: number,
  warehouses_count: number,
  last_sale_at: string | null,  // ISO datetime последней продажи, null — продаж ещё не было
}
```

`404` — магазина с таким `id` не существует.

## `POST /api/admin/tenants/{id}/suspend` и `.../unsuspend`

Без тела запроса. Ответ (`200`) — та же `TenantDetailResponse`, что и у
`GET /api/admin/tenants/{id}`, с уже обновлённым `is_suspended`. `404` —
магазин не найден.

**Блокировка действует немедленно, без задержки:**
- Владелец/сотрудники заблокированного магазина не могут залогиниться
  (`POST /api/auth/login` → `403` с сообщением «Магазин заблокирован»).
- Уже открытая сессия (существующий JWT в браузере владельца) перестаёт
  работать на **следующий же запрос** — не нужно ждать истечения токена.
  Любой `/api/*` эндпоинт, кроме `/api/auth/login`, отдаёт `403`.
- Публичная витрина магазина (`/store/{slug}`) сразу перестаёт открываться —
  ведёт себя как магазин с выключенной витриной (`404`).
- Разблокировка (`unsuspend`) отменяет все три ограничения сразу же.

**Что нужно сделать на фронте:** если где-то в панели владельца/сотрудника
ловится `403` от обычных `/api/*` эндпоинтов (не `/api/admin/*`) — стоит
показывать это как «доступ ограничен», а не как обычную ошибку авторизации,
раз теперь `403` может означать не только нехватку прав роли, но и
блокировку всего магазина.

---

## `GET /api/admin/error-logs?limit=50`

```ts
{
  errors: {
    timestamp: string,     // ISO datetime
    method: string,        // "GET" | "POST" | ...
    path: string,
    error_type: string,    // имя класса исключения, например "ValueError"
    message: string,       // текст ошибки, обрезан до 500 символов
  }[]
}
```

- Последние необработанные ошибки (500), самая новая **первая**.
- `limit` — по умолчанию 50, максимум 200 (сервер сам обрезает большее значение).
- Хранится в Redis, максимум 200 записей — старые молча вытесняются новыми,
  это диагностика последних инцидентов, не журнал аудита.
- **После перезапуска Redis-контейнера история очищается.**
- Если Redis недоступен — эндпоинт не падает, отдаёт `{"errors": []}`.

---

## Что нужно сделать на фронте

1. Отдельный приватный экран/вкладка, не в общем меню — например скрытый
   маршрут, доступный только вам напрямую по ссылке.
2. Форма логина (`login`/`password`) → сохранить `access_token` (например
   `localStorage`, отдельно от обычного пользовательского токена) → добавлять
   `Authorization: Bearer` ко всем последующим `/api/admin/*` запросам.
   Токен живёт 2 часа — на `401` показывать форму логина заново, не пытаться
   освежить токен автоматически (refresh-эндпоинта нет).
3. Блок статуса — значения из `/status`, можно поллингом раз в 5-10 секунд
   (бэкенд уже кеширует, лишней нагрузки не будет).
4. Список магазинов (`/tenants`) с переходом в карточку (`/tenants/{id}`);
   в карточке — кнопка «Заблокировать»/«Разблокировать» на suspend/unsuspend,
   с подтверждением перед блокировкой (владелец сразу теряет доступ).
5. Таблица/список последних ошибок из `/error-logs` — `timestamp`,
   `method path`, `error_type: message`.

## Ограничения текущей версии

- Нет поиска/фильтра/пагинации в списке магазинов — отдаётся весь список
  целиком (нормально при текущем масштабе, может понадобиться пагинация
  при росте числа магазинов).
- Нет пагинации логов ошибок за пределами `limit` (только последние N).
- `online_now` не агрегирован по воркерам (см. выше).
- Нет истории/графика метрик во времени — только текущий снимок на момент запроса.
- Нет refresh-токена для admin-сессии — по истечении 2 часов нужен новый логин.

---

# v2 — админ-панель платформы (задача TASK_ADMIN_PANEL_V2, часть A)

Всё ниже — под той же админской авторизацией (`Authorization: Bearer <admin token>`),
владелец магазина со своим обычным JWT получает `401`.

**Приватность.** Админ платформы видит счётчики, даты и статусы, но не
содержимое чужого бизнеса: сумм долгов по клиентам, закупочных цен, телефонов
покупателей и текстов чатов в этих ответах нет и не будет — это закрыто
тестами, которые ищут запрещённые поля в сыром ответе.

## `GET /api/admin/overview` — сводка по платформе

Кеш 60 секунд.

```ts
interface PlatformOverview {
  shops: {
    total: number; active_7d: number; active_30d: number
    new_7d: number; new_30d: number; suspended: number; storefront_on: number
  }
  users: { total: number; active_7d: number }        // сотрудники магазинов
  customers: { total: number; new_7d: number }       // покупатели витрин
  sales: {
    today_count: number; today_sum: string           // «сегодня» — по Москве
    d7_count: number; d7_sum: string
    d30_count: number; d30_sum: string
  }
  debts: { open_count: number; open_sum: string }    // агрегат, без разбивки по клиентам
  storefront: { requests_7d: number; accepted_7d: number }
  series_30d: {                                      // 31 точка: 30 суток назад + сегодня
    date: string[]; new_shops: number[]
    sales_count: number[]; active_shops: number[]
  }
}
```

«Активен» = была хотя бы одна продажа за период. Дни без событий остаются в
рядах нулями — иначе график скрыл бы простои.

## `GET /api/admin/tenants` — список магазинов

Параметры: `query`, `status` (`all|new|active|quiet|churned|suspended`),
`storefront` (`on|off`), `sort` (`last_activity|sales_30d|created_at|name`),
`limit` (≤200), `offset`. Кеш 30 секунд, сбрасывается действиями админа.

> **Ломающее изменение:** раньше отдавался `{ tenants: [...] }` с четырьмя
> полями на магазин. Теперь добавлены `total`, `counts_by_health` и агрегаты.

```ts
interface TenantListItem {
  id: number; name: string; slug: string | null; city: string | null
  created_at: string
  is_suspended: boolean; is_verified: boolean; storefront_enabled: boolean
  owner_name: string
  users_count: number; warehouses_count: number; products_count: number
  last_sale_at: string | null; last_login_at: string | null
  sales_7d: number; sales_30d: number; sales_sum_30d: string
  debts_open_count: number          // только количество, без сумм
  storefront_requests_30d: number
  health: 'new' | 'active' | 'quiet' | 'churned'
}

interface TenantListResponse {
  tenants: TenantListItem[]
  total: number                      // всего под фильтром
  counts_by_health: Record<string, number>   // для чипов, по всей платформе
}
```

**Пороги `health`** (backend/app/domain/platform/health.py):
`new` — зарегистрирован меньше 7 дней назад и продаж ещё нет; `active` —
продажа была ≤ 3 дней назад; `quiet` — 4–14 дней; `churned` — больше 14 дней
или ни одной продажи у магазина старше недели.

## `GET /api/admin/tenants/{id}` — карточка магазина

Всё из списка плюс:

```ts
interface TenantDetail extends TenantListItem {
  logo: string
  owner: { name: string; phone: string } | null
  sales_series_30d: { date: string[]; count: number[]; sum: string[] }
  users: { id: number; name: string; role: string
           is_active: boolean; last_login_at: string | null }[]   // без телефонов
  warehouses: { id: number; name: string; address: string
                show_on_storefront: boolean; positions_count: number }[]
  top_products: { id: number; name: string; sold_30d: string }[]  // 5, без выручки
  storefront: { enabled: boolean; slug: string | null
                products_on_storefront: number
                requests_30d: number; reviews_count: number }
  recent_activity: { at: string; actor_name: string
                     action: string; entity: string }[]           // 20, без details
  totals: { products: number; sales_all_time: number
            debts_open_count: number; customers_served: number }
}
```

`details` действий не отдаётся намеренно — там бывают суммы и имена клиентов
магазина.

## `GET /api/admin/status` — состояние сервера

К существующим полям добавлены блоки. **Где значение недоступно — `null`, а не
ноль:** «не знаем» и «ноль» это разные вещи, показывайте «нет данных».

```ts
interface ServerStatusV2 {
  load_avg: [number, number, number] | null
  disk_free_percent: number | null
  app: { version: string; git_sha: string        // "dev" в локальной сборке
         started_at: string | null; uptime_seconds: number | null
         workers: number }
  db: { ok: boolean; size_bytes: number | null
        connections_active: number | null; connections_max: number | null
        slowest_query_ms_1h: number | null }     // null без pg_stat_statements
  redis: { ok: boolean; used_memory: number | null
           keys: number | null; hit_rate_1h: number | null }
  uploads: { files_count: number; size_bytes: number }
  api: { rps_1h: number | null; p50_ms: number | null; p95_ms: number | null
         errors_5xx_24h: number; errors_4xx_24h: number }
  backup: { last_at: string | null; size_bytes: number | null
            offsite_ok: boolean } | null         // null — скрипт ещё не отработал
  tls: { domain: string; expires_at: string; days_left: number } | null
}
```

`p50/p95` округлены вверх до границы корзины гистограммы — читаются как «не
хуже этого». `rps/p50/p95` равны `null`, если за час не было ни одного запроса.

`backup.offsite_ok: false` означает, что внешняя копия не настроена — это
повод показать предупреждение, а не молча покрасить в зелёный.

## Ошибки

Хранятся в БД (таблица `error_log`), не в Redis: счётчики за 7 дней и вкладка
«Решённые» должны переживать перезапуск Redis. Записи старше 30 дней удаляются.

**`GET /api/admin/error-groups`** — параметры `period_days` (1–30, по умолчанию
1), `only_unresolved` (по умолчанию `true`), `error_type`, `path`.

```ts
interface ErrorGroup {
  signature: string      // числовые сегменты пути схлопнуты: /products/17 и /42 — одна группа
  type: string; path: string; method: string
  count_24h: number; count_7d: number
  first_at: string; last_at: string
  sample_id: number      // id записи для быстрого открытия деталей
  resolved: boolean
}
```

Сортировка — по `count_24h` убыванием.

**`GET /api/admin/error-groups/{signature}/entries?limit=20`** — последние
записи группы.

**`POST /api/admin/error-groups/{signature}/resolve?resolved=true`** — группа
уходит из основного списка. Записи не удаляются: вернувшаяся ошибка будет
видна как рецидив. `404`, если группы нет.

**`GET /api/admin/error-logs/{id}`** — одна запись.

```ts
interface ErrorEntry {
  id: number; created_at: string
  method: string; path: string
  error_type: string; message: string
  status_code: number | null; tenant_id: number | null
  stack: string                     // обрезан до 8000 символов
  resolved_at: string | null
}
```

Тела запроса, заголовков и персональных данных в записи нет — они не
сохраняются вовсе.

## Эксплуатация: откуда берутся backup и tls

Backend не ходит ни в `/etc/letsencrypt`, ни в каталоги бэкапов. Внешние
скрипты кладут два маленьких JSON в каталог, смонтированный read-only
(`STATUS_DIR`, по умолчанию `/opt/waysklad/status`):

- `deploy/backup.sh` → `backup.json` после каждого бэкапа;
- `deploy/tls-status-hook.sh` (certbot deploy-hook) → `tls.json` после
  обновления сертификата.

Файла нет — соответствующий блок `null`. Это нормальное состояние на свежем
сервере, а не ошибка.
