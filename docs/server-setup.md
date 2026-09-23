# Настройка сервера под ВайСклад (VPS + GitHub Actions автодеплой)

Инструкция для того, кто разворачивает сервер с нуля. Цель — чтобы после
настройки автодеплой из GitHub Actions (`.github/workflows/ci.yml`) просто
работал: пуш в `main` → тесты → `git pull` + пересборка контейнеров на
сервере.

Требования к серверу: Ubuntu 22.04/24.04 (или аналог), минимум 2 GB RAM,
публичный IP.

## 1. Базовая защита сервера

Выполняется от root при первом заходе.

```bash
apt update && apt upgrade -y

# Отдельный непривилегированный пользователь — деплой не должен идти под root
adduser deploy
usermod -aG sudo deploy
usermod -aG docker deploy   # добавится после установки Docker (шаг 2)
```

Настроить файрвол (открыты только SSH, HTTP, HTTPS):

```bash
apt install -y ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

Отключить вход по паролю и вход root по SSH — только по ключу
(`/etc/ssh/sshd_config`):

```
PermitRootLogin no
PasswordAuthentication no
```

```bash
systemctl restart sshd
```

Дальше заходить на сервер уже под `deploy`, не под root.

## 2. Установка Docker

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
```

Перезайти по SSH под `deploy`, чтобы группа `docker` применилась. Проверить:

```bash
docker run hello-world
```

## 3. Структура каталога проекта

Автодеплой в CI делает `cd $DEPLOY_PATH && git pull origin main`, поэтому
важно, чтобы каталог на сервере был обычным git-репозиторием, склонированным
с GitHub, а не залит вручную архивом.

```bash
mkdir -p /home/deploy/apps
cd /home/deploy/apps
git clone https://github.com/Raasaal511/waysklad.git
cd waysklad
git checkout main
```

Если репозиторий приватный — клонировать по SSH (см. шаг 4, тот же deploy-ключ
можно использовать и для клонирования, и для pull).

## 4. Deploy-ключ для GitHub Actions

**Ключ генерируется на твоей машине (не на сервере) и не для клонирования, а
для того, чтобы GitHub Actions мог зайти на сервер по SSH.** Это отдельный
ключ, не связанный с твоим личным SSH-ключом.

На локальной машине:

```bash
ssh-keygen -t ed25519 -f deploy_key -C "github-actions-deploy" -N ""
```

Получится два файла: `deploy_key` (приватный) и `deploy_key.pub` (публичный).

На сервере — добавить публичную часть в `authorized_keys` пользователя
`deploy`:

```bash
# на сервере, под пользователем deploy
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "СОДЕРЖИМОЕ_deploy_key.pub" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Приватный `deploy_key` уходит в GitHub Secrets (шаг 6), после чего **удалить
оба файла с локальной машины** — они не должны лежать на диске в открытом
виде дольше, чем нужно для копирования.

Ограничить, что можно делать этим ключом (по желанию, но рекомендуется) —
в `~/.ssh/authorized_keys` перед публичным ключом можно добавить restriction:

```
command="cd /home/deploy/waysklad && PREV=\$(git rev-parse HEAD) && echo Deploy previous SHA: \$PREV && git pull origin main && docker compose -f docker-compose.prod.yml build && docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head && docker compose -f docker-compose.prod.yml up -d --wait db redis backend frontend && docker compose -f docker-compose.prod.yml up -d scheduler storefront_bot certbot",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-ed25519 AAAA...
```

Это жёстко ограничивает ключ одной командой — даже если приватный ключ
утечёт, им нельзя будет сделать ничего, кроме деплоя этого проекта.

## 5. Файл `.env` на сервере

`.env` не хранится в git (см. `.gitignore`) — CI его не создаёт и не трогает,
поэтому он должен быть заведён на сервере вручную один раз и остаётся между
деплоями (docker compose просто продолжит его читать).

```bash
cd /home/deploy/waysklad
cp .env.example .env
nano .env   # заполнить реальными значениями
```

Обязательно заменить в проде:

- `POSTGRES_PASSWORD` — сгенерировать случайный пароль (например
  `openssl rand -base64 24`), не оставлять `postgres`.
- `SECRET_KEY` — случайная длинная строка (`openssl rand -hex 32`).
- `DEBUG=0` — в проде debug-режим должен быть выключен.
- `DATABASE_URL` — обычно не меняется (`db` — имя сервиса в docker-сети),
  но пароль в строке подключения должен совпадать с `POSTGRES_PASSWORD`.
- `TELEGRAM_BOT_TOKEN` — боевой токен бота.

Права на файл — только владельцу:

```bash
chmod 600 .env
```

## 6. Секреты в GitHub

В репозитории на GitHub: **Settings → Secrets and variables → Actions → New
repository secret**. Добавить:

| Secret            | Значение                                                        |
|--------------------|-------------------------------------------------------------------|
| `DEPLOY_HOST`      | IP-адрес или домен сервера                                        |
| `DEPLOY_USER`      | `deploy`                                                           |
| `DEPLOY_SSH_KEY`   | содержимое приватного файла `deploy_key` целиком, включая заголовки |
| `DEPLOY_PATH`      | `/home/deploy/waysklad`                                       |

## 7. Первый запуск

Первый раз стек поднимается вручную на сервере (чтобы сразу проверить, что
всё собирается и БД накатывает миграции) — дальше это уже будет делать CI.

```bash
cd /home/deploy/waysklad
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --wait db redis backend frontend scheduler storefront_bot
docker compose -f docker-compose.prod.yml up -d certbot
```

Проверить:

```bash
curl http://localhost/api/health
# {"status":"ok"}
```

## 8. Бэкапы БД

В репозитории уже есть `deploy/backup.sh` — ежедневный дамп Postgres с
хранением последних 30 копий. Добавить в cron под пользователем `deploy`:

```bash
crontab -e
```

```
0 3 * * * /home/deploy/waysklad/deploy/backup.sh
```

**Важно:** без дополнительной настройки бэкапы складываются только локально
на тот же сервер — это не защищает от потери самого сервера. Скрипт умеет
копировать на внешнее хранилище через `rclone`, если задать
`BACKUP_RCLONE_REMOTE` в `.env` (см. `.env.example`) — до первого реального
клиента стоит это настроить:

```bash
# один раз на хосте, интерактивно — любое S3-совместимое хранилище
# (Backblaze B2, Yandex Object Storage, ...) или другой сервер по SFTP
rclone config

# проверить, что remote настроен и виден
rclone lsd <имя-remote>:
```

Затем в `.env`:

```
BACKUP_RCLONE_REMOTE=<имя-remote>:<бакет-или-путь>
```

После этого `backup.sh` при каждом запуске копирует свежий дамп и архив
фото на remote, а по воскресеньям дополнительно кладёт их в `<remote>/weekly`
с хранением 90 дней — так локальная ежедневная ротация (30 копий) не
единственная защита от порчи БД, которую заметили не сразу. Если
`BACKUP_RCLONE_REMOTE` не задан, скрипт не падает, но пишет предупреждение
в лог cron — не должно молчать об этом до первого реального инцидента.

Проверка восстановления (в отдельную БД, не в бой):

```bash
./deploy/backup.sh
./deploy/restore.sh backups/waysklad-….sql.gz backups/waysklad-uploads-….tgz
```

Полный сценарий после потери сервера — `docs/RESTORE.md`.

## 9. Проверка автодеплоя

После того как всё выше настроено — сделать любой пуш в `main` (или смёрджить
PR) и проверить во вкладке **Actions** на GitHub, что job `deploy` прошёл
зелёным. На сервере после этого должны обновиться контейнеры:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
```

## Как это защищено от конфликтов при параллельных пушах

- CI считает деплой только после того, как оба джоба тестов (`backend-tests`,
  `frontend-checks`) прошли зелёным — сломанный код на прод не попадёт.
- Деплой — это `git pull` строго веткой `main`, без merge-конфликтов: на
  сервере никогда не должно быть локальных изменений в рабочей копии
  (`git status` должен быть чистым). Если на сервере что-то правили руками
  напрямую в файлах репозитория — это единственный способ сломать
  `git pull`; все конфигурационные правки должны идти через `.env`, а не
  через правку закоммиченных файлов на сервере.
- GitHub Actions запускает деплои по очереди для одного и того же workflow
  (не параллельно), так что два пуша подряд не столкнутся друг с другом на
  сервере.

## Откат

В логе джобы деплоя печатается `Deploy previous SHA: <sha>` — коммит до
`git pull`. Откат на сервере одной серией команд:

```bash
cd /home/deploy/waysklad
git checkout <sha>
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --wait db redis backend frontend scheduler storefront_bot
docker compose -f docker-compose.prod.yml up -d certbot
```

Миграции в этом релизе только добавляющие — старый код совместим с новой
схемой, откат кода без downgrade миграций безопасен. Если откатываетесь
через коммит, где схемы ещё нет нужных колонок, и уже накатили миграции
вперёд — не делайте `alembic downgrade`; оставьте схему, откатитесь только
код на совместимый SHA.
