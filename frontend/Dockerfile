FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

RUN apk add --no-cache openssl

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# HTTP, не HTTPS: 127.0.0.1 без SNI на HTTPS-порту попадает в default_server
# nginx.conf (Host не совпал ни с одним server_name) — он отвечает 444, wget
# видит это как обрыв соединения, healthcheck всегда красный независимо от
# реального состояния nginx. Host-заголовок нужен по той же причине — на
# порту 80 без него запрос тоже уходит в default_server.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD wget -qO- http://127.0.0.1/ --header="Host: waysklad.gwensoft.ru" || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
