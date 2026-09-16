#!/bin/sh
set -e

CERT_DIR="/etc/letsencrypt/live/waysklad.gwensoft.ru"

# nginx с конфигом на 443 не стартует, если файлов сертификата ещё нет
# (домен только что поднят, certbot ни разу не отработал) — кладём временный
# self-signed, чтобы nginx поднялся и certbot смог пройти HTTP-01 challenge
# через него же. certbot-сервис (см. docker-compose.prod.yml) сам чистит эту
# директорию перед первой попыткой certonly — она не в штатном формате
# certbot (нет archive/), и он откажется сохранить туда настоящий сертификат.
if [ ! -f "$CERT_DIR/fullchain.pem" ]; then
    echo "Сертификат не найден, генерирую временный self-signed для старта nginx..."
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -days 1 \
        -newkey rsa:2048 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/CN=waysklad.gwensoft.ru"
fi

# certbot продлевает сертификат в отдельном контейнере (тот же volume), nginx
# сам не подхватывает подмену файла — раз в 6 часов делаем reload (дёшево и
# безопасно, если сертификат не менялся: не рвёт активные соединения).
(
    while true; do
        sleep 6h
        nginx -s reload
    done
) &

exec "$@"
