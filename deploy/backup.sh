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

# храним последние 30 ежедневных копий локально
ls -1t backups/waysklad-*.sql.gz | tail -n +31 | xargs -r rm

# Копия на внешнее хранилище — без неё бэкап не переживает потерю/кражу
# самого сервера, только его "случайную" порчу (см. README §6.5, п.13 плана
# «потеря данных = потеря доверия навсегда»). Включается заданием
# BACKUP_RCLONE_REMOTE в .env (пусто по умолчанию — копирования нет, только
# предупреждение в лог, чтобы не молчать об этом до первого реального
# инцидента). rclone настраивается один раз на хосте (rclone config) под
# любое S3-совместимое хранилище/другой сервер по SFTP — сюда попадает уже
# готовое имя remote, секреты остаются в rclone.conf, не в этом репозитории.
if [ -n "${BACKUP_RCLONE_REMOTE:-}" ]; then
  rclone copy "$file" "$BACKUP_RCLONE_REMOTE" --quiet

  # недельная ротация НА REMOTE — отдельно от локальной (30 ежедневных):
  # локально держим глубину для быстрого отката, на remote — более редкие
  # снимки на случай, если порча БД останется незамеченной больше месяца.
  # Раз в неделю (первый прогон после полуночи воскресенья — day-of-week=0
  # в `date +%w`) кладём тот же файл ещё и в weekly/, откуда чистим старше 90 дней.
  if [ "$(date +%w)" = "0" ]; then
    rclone copy "$file" "${BACKUP_RCLONE_REMOTE}/weekly" --quiet
    rclone delete "${BACKUP_RCLONE_REMOTE}/weekly" --min-age 90d --quiet
  fi
else
  echo "WARNING: BACKUP_RCLONE_REMOTE не задан — бэкап только локальный, не переживёт потерю сервера" >&2
fi
