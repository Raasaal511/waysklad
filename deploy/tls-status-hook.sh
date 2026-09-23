#!/usr/bin/env bash
# Certbot deploy-hook: пишет срок действия сертификата туда, откуда его
# читает админ-панель. Backend в /etc/letsencrypt не ходит — у процесса
# приложения нет причин иметь доступ к приватным ключам.
#
# Установка (один раз на хосте):
#   sudo cp deploy/tls-status-hook.sh /etc/letsencrypt/renewal-hooks/deploy/waysklad-status.sh
#   sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/waysklad-status.sh
# и однократный прогон после первого выпуска, чтобы файл появился сразу:
#   sudo DOMAIN=waysklad.gwensoft.ru /etc/letsencrypt/renewal-hooks/deploy/waysklad-status.sh
set -euo pipefail

DOMAIN="${DOMAIN:-${RENEWED_DOMAINS%% *}}"
STATUS_DIR="${BACKUP_STATUS_DIR:-/opt/waysklad/status}"
CERT="${RENEWED_LINEAGE:-/etc/letsencrypt/live/$DOMAIN}/cert.pem"

[ -f "$CERT" ] || { echo "нет сертификата: $CERT" >&2; exit 0; }

expires_raw="$(openssl x509 -enddate -noout -in "$CERT" | cut -d= -f2)"
expires_iso="$(date -u -d "$expires_raw" +%Y-%m-%dT%H:%M:%S+00:00 2>/dev/null \
  || date -u -j -f "%b %d %T %Y %Z" "$expires_raw" +%Y-%m-%dT%H:%M:%S+00:00)"

mkdir -p "$STATUS_DIR"
cat > "$STATUS_DIR/tls.json" <<JSON
{
  "domain": "$DOMAIN",
  "expires_at": "$expires_iso"
}
JSON
