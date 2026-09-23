FROM python:3.12-slim

# Версия сборки для админки («Эксплуатация»). Дефолты заданы, чтобы локальная
# сборка без --build-arg не падала: docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD)
ARG GIT_SHA=dev
ARG BUILD_TIME=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GIT_SHA=$GIT_SHA \
    BUILD_TIME=$BUILD_TIME

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

# --proxy-headers + --forwarded-allow-ips="*" — доверяем X-Forwarded-For/X-Real-IP
# от nginx (единственный, кто достучится до backend:8000 внутри docker-сети,
# см. frontend/nginx.conf). Без этого request.client.host — IP самого nginx
# для ВСЕХ клиентов разом, и rate_limit.py (лимит по IP) на деле лимитирует
# всех пользователей одним общим счётчиком, а не по отдельности.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
