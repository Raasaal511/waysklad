#!/usr/bin/env bash
# Восстановление из бэкапа. По умолчанию — в отдельную БД waysklad_restore_check
# (боевую не трогаем). Флаг --into-prod требует явного подтверждения «ДА».
#
# Использование:
#   ./deploy/restore.sh backups/waysklad-….sql.gz [backups/waysklad-uploads-….tgz]
#   ./deploy/restore.sh --into-prod backups/waysklad-….sql.gz [uploads.tgz]
#
# Переменные окружения:
#   RESTORE_DB             — имя проверочной БД (по умолчанию waysklad_restore_check;
#                            deploy/rehearse-migrations.sh передаёт waysklad_rehearsal).
#                            Совпадать с боевой нельзя — для этого есть --into-prod.
#   WAYSKLAD_COMPOSE_FILE  — compose-файл (по умолчанию docker-compose.prod.yml;
#                            для локальной проверки — docker-compose.yml).
#   WAYSKLAD_PROJECT_DIR   — каталог с .env и запущенным compose-проектом
#                            (по умолчанию — корень репозитория этого скрипта).
set -euo pipefail

cd "${WAYSKLAD_PROJECT_DIR:-$(dirname "$0")/..}"
source .env

INTO_PROD=0
if [ "${1:-}" = "--into-prod" ]; then
  INTO_PROD=1
  shift
fi

DUMP="${1:-}"
UPLOADS="${2:-}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "Нужен путь к дампу: $0 [--into-prod] <dump.sql.gz> [uploads.tgz]" >&2
  exit 1
fi

COMPOSE=(docker compose -f "${WAYSKLAD_COMPOSE_FILE:-docker-compose.prod.yml}")
PSQL=("${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER")

if [ "$INTO_PROD" -eq 1 ]; then
  echo "ВНИМАНИЕ: восстановление в БОЕВУЮ БД «${POSTGRES_DB}»."
  echo "Все текущие данные будут заменены."
  printf "Введите ДА для продолжения: "
  read -r confirm
  if [ "$confirm" != "ДА" ]; then
    echo "Отменено."
    exit 1
  fi
  TARGET_DB="$POSTGRES_DB"
else
  TARGET_DB="${RESTORE_DB:-waysklad_restore_check}"
  if ! [[ "$TARGET_DB" =~ ^[a-z_][a-z0-9_]*$ ]]; then
    echo "Недопустимое имя проверочной БД: «${TARGET_DB}»" >&2
    exit 1
  fi
  if [ "$TARGET_DB" = "$POSTGRES_DB" ]; then
    echo "RESTORE_DB совпадает с боевой БД «${POSTGRES_DB}». Для боевой — только --into-prod." >&2
    exit 1
  fi
  echo "Восстановление в проверочную БД «${TARGET_DB}»…"
  "${PSQL[@]}" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname = '${TARGET_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${TARGET_DB};
CREATE DATABASE ${TARGET_DB} OWNER ${POSTGRES_USER};
SQL
fi

echo "Импорт дампа → ${TARGET_DB}…"
gunzip -c "$DUMP" | "${COMPOSE[@]}" exec -T db \
  psql -U "$POSTGRES_USER" -d "$TARGET_DB" -v ON_ERROR_STOP=1 -q

echo "Строки в ключевых таблицах (${TARGET_DB}):"
"${PSQL[@]}" -d "$TARGET_DB" -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'tenants' AS table, count(*)::text AS rows FROM tenants
UNION ALL SELECT 'products', count(*)::text FROM products
UNION ALL SELECT 'sales', count(*)::text FROM sales
UNION ALL SELECT 'debts', count(*)::text FROM debts
ORDER BY 1;
SQL

if [ -n "$UPLOADS" ]; then
  if [ ! -f "$UPLOADS" ]; then
    echo "Архив фото не найден: $UPLOADS" >&2
    exit 1
  fi
  if [ "$INTO_PROD" -eq 1 ]; then
    echo "Распаковка фото в volume uploads…"
    "${COMPOSE[@]}" exec -T backend sh -c 'rm -rf /app/uploads/*'
    cat "$UPLOADS" | "${COMPOSE[@]}" exec -T backend tar xzf - -C /app
    echo "Фото распакованы в /app/uploads."
  else
    echo "Проверка архива фото (без записи в volume)…"
    tar tzf "$UPLOADS" | head -n 20
    echo "… ($(tar tzf "$UPLOADS" | wc -l | tr -d ' ') путей в архиве)"
  fi
fi

if [ "$INTO_PROD" -eq 0 ]; then
  echo
  echo "Проверка завершена. Боевая БД не изменялась."
  echo "Удалить проверочную: ${COMPOSE[*]} exec -T db psql -U \$POSTGRES_USER -d postgres -c 'DROP DATABASE ${TARGET_DB};'"
fi
