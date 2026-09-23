#!/usr/bin/env bash
# Репетиция миграций на копии боевых данных. Боевую БД не трогает.
#
# 1. Восстанавливает дамп в отдельную БД waysklad_rehearsal (через restore.sh).
# 2. Прогоняет против неё `alembic upgrade head`.
# 3. Печатает ревизию и число строк в ключевых таблицах до и после, время миграций.
#
# Использование:
#   ./deploy/rehearse-migrations.sh [--image IMAGE] backups/waysklad-….sql.gz
#
#   --image IMAGE  образ backend, из которого запускать миграции. Нужен, чтобы
#                  проверить миграции нового релиза, не пересобирая боевой образ:
#                  соберите образ из новой ветки под своим тегом и передайте сюда.
#                  Без флага — текущий образ сервиса backend из compose-файла.
#
# Переменные окружения:
#   WAYSKLAD_COMPOSE_FILE  compose-файл (по умолчанию docker-compose.prod.yml;
#                          для локальной проверки — docker-compose.yml).
#   WAYSKLAD_PROJECT_DIR   каталог с .env и запущенным compose-проектом (по умолчанию —
#                          корень репозитория этого скрипта). Позволяет запустить скрипт
#                          из временной копии новой ветки против боевого каталога, не
#                          меняя в боевом checkout ни одного файла.
#
# Проверочная БД остаётся после прогона, чтобы в неё можно было заглянуть;
# команда удаления печатается в конце.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REHEARSAL_DB="waysklad_rehearsal"
TABLES="tenants users products sales debts reviews"

IMAGE=""
if [ "${1:-}" = "--image" ]; then
  IMAGE="${2:-}"
  if [ -z "$IMAGE" ]; then
    echo "После --image нужно имя образа" >&2
    exit 1
  fi
  shift 2
fi

DUMP="${1:-}"
if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "Нужен путь к дампу: $0 [--image IMAGE] <dump.sql.gz>" >&2
  exit 1
fi
# Абсолютный путь — ниже меняем каталог.
DUMP="$(cd "$(dirname "$DUMP")" && pwd)/$(basename "$DUMP")"

cd "${WAYSKLAD_PROJECT_DIR:-$SCRIPT_DIR/..}"
source .env

if [ "$REHEARSAL_DB" = "$POSTGRES_DB" ]; then
  echo "Проверочная БД совпадает с боевой «${POSTGRES_DB}» — отказ." >&2
  exit 1
fi

COMPOSE_FILE_PATH="${WAYSKLAD_COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE=(docker compose -f "$COMPOSE_FILE_PATH")
PSQL=("${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d "$REHEARSAL_DB" -v ON_ERROR_STOP=1 -qAt)

# Тот же DATABASE_URL, что у backend, но с другим именем БД.
REHEARSAL_URL="${DATABASE_URL%/*}/${REHEARSAL_DB}"

# Другой образ — через временный override: env_file, environment и сеть те же,
# что у боевого backend, отличается только образ.
RUN_COMPOSE=("${COMPOSE[@]}")
if [ -n "$IMAGE" ]; then
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Образ «${IMAGE}» не найден. Соберите его: docker build -t ${IMAGE} <путь к backend>" >&2
    exit 1
  fi
  OVERRIDE_FILE="$(mktemp)"
  trap 'rm -f "$OVERRIDE_FILE"' EXIT
  printf 'services:\n  backend:\n    image: %s\n' "$IMAGE" >"$OVERRIDE_FILE"
  RUN_COMPOSE+=(-f "$OVERRIDE_FILE")
fi

# Число строк по списку таблиц. Таблицы, которой ещё нет (появится в миграции),
# печатается как «нет таблицы» — to_regclass не даёт запросу упасть.
count_rows() {
  local list
  list="$(printf "'%s'," $TABLES)"
  "${PSQL[@]}" <<SQL
SELECT CASE
         WHEN to_regclass('public.' || t) IS NULL THEN 'нет таблицы'
         ELSE (xpath('/row/c/text()',
                     query_to_xml(format('SELECT count(*) AS c FROM %I', t), false, true, '')))[1]::text
       END
FROM unnest(ARRAY[${list%,}]) WITH ORDINALITY AS x(t, n)
ORDER BY n;
SQL
}

current_revision() {
  "${PSQL[@]}" -c "SELECT string_agg(version_num, ',') FROM alembic_version" 2>/dev/null || echo "нет alembic_version"
}

# restore.sh — из той же копии, что и этот скрипт (он умеет RESTORE_DB).
RESTORE_DB="$REHEARSAL_DB" WAYSKLAD_COMPOSE_FILE="$COMPOSE_FILE_PATH" WAYSKLAD_PROJECT_DIR="$PWD" \
  "$SCRIPT_DIR/restore.sh" "$DUMP"

echo
echo "=== Репетиция миграций на «${REHEARSAL_DB}» ==="
REV_BEFORE="$(current_revision)"
COUNTS_BEFORE="$(count_rows)"

# Время меряем внутри контейнера: без запуска самого контейнера.
MIGRATE_PY='
import subprocess, sys, time
start = time.perf_counter()
code = subprocess.call(["alembic", "upgrade", "head"])
print(f"MIGRATION_SECONDS={time.perf_counter() - start:.2f}", flush=True)
sys.exit(code)
'
set +e
MIGRATE_OUT="$("${RUN_COMPOSE[@]}" run --rm --no-deps -T -e DATABASE_URL="$REHEARSAL_URL" \
  backend python -c "$MIGRATE_PY" 2>&1)"
MIGRATE_CODE=$?
set -e
echo "$MIGRATE_OUT" | grep -v '^MIGRATION_SECONDS=' || true
SECONDS_SPENT="$(echo "$MIGRATE_OUT" | sed -n 's/^MIGRATION_SECONDS=//p' | tail -n 1)"

REV_AFTER="$(current_revision)"
COUNTS_AFTER="$(count_rows)"

echo
echo "Ревизия до:     ${REV_BEFORE}"
echo "Ревизия после:  ${REV_AFTER}"
echo "Время миграций: ${SECONDS_SPENT:-?} с"
echo
# Заголовок литералом: printf в bash 3.2 считает ширину кириллицы в байтах.
echo "таблица                До          После"
paste <(printf '%s\n' $TABLES) <(echo "$COUNTS_BEFORE") <(echo "$COUNTS_AFTER") |
  while IFS=$'\t' read -r table before after; do
    printf '%-10s %14s %14s\n' "$table" "$before" "$after"
  done

echo
if [ "$MIGRATE_CODE" -ne 0 ]; then
  echo "МИГРАЦИИ УПАЛИ (код ${MIGRATE_CODE}). Вывод alembic — выше. Деплоить нельзя." >&2
  exit "$MIGRATE_CODE"
fi
echo "Миграции прошли. Боевая БД «${POSTGRES_DB}» не изменялась."
echo "Удалить проверочную: ${COMPOSE[*]} exec -T db psql -U \$POSTGRES_USER -d postgres -c 'DROP DATABASE ${REHEARSAL_DB};'"
