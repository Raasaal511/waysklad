# Запуск через Docker

## Разработка

```
cp .env.example .env      # заполнить SECRET_KEY и т.п.
docker compose up -d
docker compose exec backend alembic upgrade head   # только при первом запуске / новом volume
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
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head   # первый запуск
```

Единственная точка входа — порт 80 (сервис `frontend`): nginx раздаёт собранную
статику React-приложения и проксирует `/api` и `/uploads` на `backend`.
`backend` и `db` портов наружу не публикуют.

## После добавления новой Alembic-миграции

```
docker compose exec backend alembic upgrade head
```
