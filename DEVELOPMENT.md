# Запуск через Docker

## Разработка

```
cp .env.example .env      # заполнить SECRET_KEY и т.п.
docker compose up -d
docker compose exec backend alembic upgrade head   # при первом запуске и после каждой новой миграции
```

- Фронтенд (Vite dev-сервер с hot-reload): http://localhost:5173
- Бэкенд напрямую: http://localhost:8000/api
- Postgres напрямую (для DBeaver/psql): localhost:55432

Порт Postgres (55432) намеренно нестандартный — 5432 на машине разработчика
часто занят локальным Postgres.app. Фронтенд и бэкенд используют свои
стандартные порты (5173/8000) — если что-то на хосте уже их занимает,
`docker compose up` откажется поднять соответствующий контейнер. Фронтенд
обращается к бэкенду через встроенный Vite-прокси (`/api` → `backend:8000`
внутри docker-сети), поэтому в браузере достаточно ходить только на 5173.

## Продакшн

```
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

`alembic upgrade head` идемпотентен — выполнять его нужно при **каждом**
деплое с новыми миграциями, не только при первом запуске (через CI/CD это
делается автоматически, см. `.github/workflows/ci.yml`, job `deploy`; при
ручном деплое — не забыть этот шаг).

Точка входа — сервис `frontend`: nginx раздаёт собранную статику React-приложения
и проксирует `/api` и `/uploads` на `backend`. `backend` и `db` портов наружу не
публикуют.

Порт 80 отдаёт только ACME-challenge и редиректит остальное на HTTPS (443).
Сертификат Let's Encrypt получает и продлевает сервис `certbot` (нужен домен,
уже указывающий на сервер, и `CERTBOT_EMAIL` в `.env`) — до первого успешного
выпуска `frontend` временно поднимается на self-signed сертификате
(`frontend/docker-entrypoint.sh`), чтобы nginx вообще стартовал и пропустил
через себя ACME-challenge.

## После добавления новой Alembic-миграции (dev)

```
docker compose exec backend alembic upgrade head
```
