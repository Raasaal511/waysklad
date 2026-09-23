#!/usr/bin/env bash
# Ежедневный бэкап БД + фото товаров. Добавить в cron на хосте:
#   0 3 * * * /path/to/waysklad/deploy/backup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p backups

source .env
stamp=$(date +%Y-%m-%d_%H-%M)
db_file="backups/waysklad-${stamp}.sql.gz"
uploads_file="backups/waysklad-uploads-${stamp}.tgz"

docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$db_file"

# Фото через уже смонтированный volume backend — без имени volume на хосте
docker compose -f docker-compose.prod.yml exec -T backend \
  tar czf - -C /app uploads > "$uploads_file"

# храним последние 30 ежедневных копий локально (дамп и архив фото отдельно)
ls -1t backups/waysklad-*.sql.gz 2>/dev/null | tail -n +31 | xargs -r rm
ls -1t backups/waysklad-uploads-*.tgz 2>/dev/null | tail -n +31 | xargs -r rm

# Копия на внешнее хранилище — без неё бэкап не переживает потерю/кражу
# самого сервера, только его "случайную" порчу (см. README §6.5, п.13 плана
# «потеря данных = потеря доверия навсегда»). Включается заданием
# BACKUP_RCLONE_REMOTE в .env (пусто по умолчанию — копирования нет, только
# предупреждение в лог, чтобы не молчать об этом до первого реального
# инцидента). rclone настраивается один раз на хосте (rclone config) под
# любое S3-совместимое хранилище/другой сервер по SFTP — сюда попадает уже
# готовое имя remote, секреты остаются в rclone.conf, не в этом репозитории.
if [ -n "${BACKUP_RCLONE_REMOTE:-}" ]; then
  rclone copy "$db_file" "$BACKUP_RCLONE_REMOTE" --quiet
  rclone copy "$uploads_file" "$BACKUP_RCLONE_REMOTE" --quiet

  # недельная ротация НА REMOTE — отдельно от локальной (30 ежедневных):
  # локально держим глубину для быстрого отката, на remote — более редкие
  # снимки на случай, если порча БД останется незамеченной больше месяца.
  # Раз в неделю (первый прогон после полуночи воскресенья — day-of-week=0
  # в `date +%w`) кладём тот же файл ещё и в weekly/, откуда чистим старше 90 дней.
  if [ "$(date +%w)" = "0" ]; then
    rclone copy "$db_file" "${BACKUP_RCLONE_REMOTE}/weekly" --quiet
    rclone copy "$uploads_file" "${BACKUP_RCLONE_REMOTE}/weekly" --quiet
    rclone delete "${BACKUP_RCLONE_REMOTE}/weekly" --min-age 90d --quiet
  fi
else
  echo "WARNING: BACKUP_RCLONE_REMOTE не задан — бэкап только локальный, не переживёт потерю сервера" >&2
fi

filesize() {
  stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}

# Метаданные для админ-панели: backend их только читает и сам никуда не лезет
# (см. infrastructure/observability/status_files.py). offsite_ok честно false,
# пока BACKUP_RCLONE_REMOTE не задан — админ должен видеть, что внешней копии
# нет, а не догадываться об этом после потери сервера.
STATUS_DIR="${BACKUP_STATUS_DIR:-/opt/waysklad/status}"
mkdir -p "$STATUS_DIR"
offsite="false"
[ -n "${BACKUP_RCLONE_REMOTE:-}" ] && offsite="true"
cat > "$STATUS_DIR/backup.json" <<JSON
{
  "last_at": "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)",
  "size_bytes": $(filesize "$db_file"),
  "uploads_size_bytes": $(filesize "$uploads_file"),
  "offsite_ok": $offsite
}
JSON
