# Сессия 17 — Docker для фронтенда, полный стек в контейнерах

**Дата:** 2026-08-05
**Этап плана:** инфраструктура (после каркаса фронтенда, сессия 16)

## Контекст
Пользователь явно попросил запуск через Docker, «правильно настроенный» —
до этой сессии фронтенд не был докеризован вообще, а `docker-compose.prod.yml`
использовал отдельный голый `nginx`-сервис, проксирующий всё на `backend`
(конфиг никогда не раздавал статику фронтенда, потому что фронтенда не
существовало).

## Что сделано
- **`frontend/Dockerfile.dev`** — Vite dev-сервер с hot-reload (`npm run dev
  --host 0.0.0.0`), volume-монтирование исходников (аналогично паттерну
  `backend`).
- **`frontend/Dockerfile`** (prod) — multi-stage: `node:22-alpine` собирает
  `npm run build`, финальный образ — `nginx:alpine`, раздаёт `dist/`.
- **`frontend/nginx.conf`** — `location /api/` и `/uploads/` проксируют на
  `backend:8000` (внутренняя docker-сеть), `location /` — `try_files ... /
  index.html` (обязательный SPA-fallback для client-side роутинга
  react-router, иначе прямой заход на `/products` даёт 404 у голого nginx).
- **`vite.config.ts`**: `server.proxy['/api']` — прокси `/api` на
  `VITE_PROXY_TARGET` (по умолчанию `localhost:8000`, в docker-сети
  переопределяется на `http://backend:8000`). Это убирает CORS полностью:
  бэкенд не настроен на CORS-заголовки вообще, а через прокси браузер видит
  единый origin и в dev, и в prod.
- **`docker-compose.yml`** (dev): добавлен сервис `frontend` (Dockerfile.dev,
  volume на исходники + анонимный volume на `node_modules`, чтобы не
  затирался хостовым bind mount). Порты `db` (5432→55432) и `backend`
  (8000→18000) изменены на нестандартные — при живом тестировании оба
  стандартных порта оказались заняты другими локальными сервисами на машине
  (Postgres.app и сторонний docker-контейнер `cache_api-backend`); внутри
  docker-сети сервисы по-прежнему обращаются друг к другу по внутренним портам
  (`db:5432`, `backend:8000`) — смена касается только host-проброса.
- **`docker-compose.prod.yml`**: сервис `nginx` заменён на `frontend` (build
  из `./frontend`, единственный, кто публикует порт `80`); `deploy/nginx.conf`
  удалён как мёртвый конфиг (роль перешла к `frontend/nginx.conf`).
- **`DEVELOPMENT.md`** (новый, в корне, НЕ в `docs/` — тот в `.gitignore`) —
  практическая шпаргалка запуска: `docker compose up -d` +
  обязательный `alembic upgrade head` при первом запуске/новом volume
  (без этого шага бэкенд падает с `UndefinedTable` — засвидетельствовано
  вживую при первом поднятии стека).

## Проверено — реальный запуск, не только синтаксис
- `docker compose config` / `docker compose -f docker-compose.prod.yml config`
  — оба валидны.
- **Dev-стек поднят вживую**: `docker compose up -d --build` — все три
  контейнера (`db`, `backend`, `frontend`) стартовали и прошли healthcheck.
  `curl http://localhost:5173/api/health` → `{"status":"ok"}` — подтверждает,
  что Vite-прокси реально доходит через docker-сеть до бэкенда. Полная
  регистрация магазина через `POST /api/auth/register` **через фронтенд-прокси**
  (не напрямую к бэкенду) — успешна, вернула JWT.
- **Prod-стек поднят вживую**: `docker compose -f docker-compose.prod.yml up -d
  --build` — `frontend` (единственный с портом 80), `backend`/`db` без внешних
  портов (как и задумано для прода). `curl http://localhost/api/health` через
  nginx-прокси фронтенда — `200`. Полная регистрация магазина через порт 80 —
  успешна. SPA-fallback проверен явно: `curl http://localhost/some-client-route`
  → `200` с `index.html`, не `404`.
- По ходу поймал и исправил реальную ошибку первого запуска (пустой volume БД
  без миграций → `UndefinedTable: relation "users" does not exist` при первой
  регистрации) — задокументировано в `DEVELOPMENT.md` как обязательный шаг.

## Дальше
Docker-запуск полностью рабочий для dev и prod. Следующий шаг по фронтенду —
экраны по сценариям README (начиная с быстрой продажи), плюс реальные
PWA-иконки (пока только пути в манифесте, файлов нет — см. сессию 16).
