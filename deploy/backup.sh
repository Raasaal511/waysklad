#!/usr/bin/env bash
# Ежедневный бэкап БД. Добавить в cron на хосте:
#   0 3 * * * /path/to/waysklad/deploy/backup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p backups

source .env
stamp=$(date +%Y-%m-%d_%H-%M)
file="backups/waysklad-${stamp}.sql.gz"

docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$file"

# храним последние 30 копий
ls -1t backups/waysklad-*.sql.gz | tail -n +31 | xargs -r rm

# TODO: копия на внешнее хранилище (rclone/scp) — обязательно до пилота
