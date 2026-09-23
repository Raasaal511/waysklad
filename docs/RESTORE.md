# Восстановление ВайСклад после потери сервера

Кратко, командами. Предполагается, что есть свежий дамп
`waysklad-….sql.gz` и архив фото `waysklad-uploads-….tgz` (локально или в
rclone-remote).

## 1. Новый VPS

По `docs/server-setup.md`: пользователь `deploy`, Docker, файрвол, клон
репозитория на `main`, `.env` с боевыми секретами (не дефолтными).

```bash
cd /home/deploy/apps/waysklad
cp .env.example .env
nano .env   # POSTGRES_PASSWORD, SECRET_KEY, TELEGRAM_*, BACKUP_RCLONE_REMOTE…
chmod 600 .env
```

## 2. Поднять инфраструктуру без приложения

```bash
docker compose -f docker-compose.prod.yml up -d db redis
# дождаться healthy
docker compose -f docker-compose.prod.yml ps
```

## 3. Скачать бэкап

```bash
mkdir -p backups
# из rclone, если бэкап там:
rclone copy "$BACKUP_RCLONE_REMOTE" ./backups --include 'waysklad-*.sql.gz' --include 'waysklad-uploads-*.tgz' --max-age 7d
ls -lt backups/ | head
```

## 4. Восстановить БД и фото в прод

Сначала проверочный прогон (отдельная БД, прод не трогает):

```bash
chmod +x deploy/restore.sh
./deploy/restore.sh backups/waysklad-YYYY-MM-DD_HH-MM.sql.gz backups/waysklad-uploads-YYYY-MM-DD_HH-MM.tgz
```

Сверить числа строк с тем, что было до аварии (если записывали). Затем в бой:

```bash
./deploy/restore.sh --into-prod backups/waysklad-….sql.gz backups/waysklad-uploads-….tgz
# подтверждение: ДА
```

## 5. Миграции и сервисы

Даже если дамп свежий — догнать схему:

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --wait db redis backend frontend scheduler storefront_bot
docker compose -f docker-compose.prod.yml up -d certbot
curl -s http://localhost/api/health
docker compose -f docker-compose.prod.yml exec -T backend alembic current
```

## 6. DNS

A-запись домена на IP нового VPS. **Без оранжевого облака Cloudflare**
(серое облако / DNS не в CF) — иначе у части провайдеров в РФ сайт не
откроется. Дождаться выпуска сертификата certbot (логи `certbot`).

## 7. Проверка

- вход владельца, список товаров с фото;
- одна тестовая продажа;
- `deploy/backup.sh` отрабатывает и пишет `backup.json`.

## 8. Репетиция миграций перед релизом

Перед вливанием develop в main (CI сразу деплоит main) прогоните миграции
новой ветки на копии боевых данных. Боевая БД и боевой checkout не меняются:
дамп восстанавливается в отдельную БД `waysklad_rehearsal`, а скрипт и образ
backend берутся из временной копии develop в `/tmp`.

```bash
cd /home/deploy/apps/waysklad
./deploy/backup.sh                                    # свежий дамп в backups/
git fetch origin develop
git worktree add --detach /tmp/waysklad-next origin/develop
docker build -t waysklad-backend:rehearsal /tmp/waysklad-next/backend
WAYSKLAD_PROJECT_DIR=/home/deploy/apps/waysklad \
  /tmp/waysklad-next/deploy/rehearse-migrations.sh --image waysklad-backend:rehearsal \
  "$(ls -1t backups/waysklad-*.sql.gz | head -n 1)"
```

Скрипт печатает ревизию до и после, время `alembic upgrade head` и число строк в
tenants, users, products, sales, debts, reviews до и после. Если миграции
упали, он пишет «МИГРАЦИИ УПАЛИ» и выходит с ненулевым кодом: вливать нельзя.

Уборка после проверки:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE waysklad_rehearsal;"'
git worktree remove --force /tmp/waysklad-next
docker image rm waysklad-backend:rehearsal
```

Сборка образа на однопроцессорном сервере занимает несколько минут и нагружает
CPU, поэтому лучше запускать её вне часов пик. Копия БД временно занимает
столько же места на диске, сколько боевая.
