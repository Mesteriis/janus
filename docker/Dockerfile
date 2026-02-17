# syntax=docker/dockerfile:1.7

ARG CADDY_VERSION=2.10.2
ARG PYTHON_VERSION=3.14-slim
ARG NODE_VERSION=20-alpine

############################
# 1) Frontend build (Vite)
############################
FROM node:${NODE_VERSION} AS frontend
WORKDIR /frontend

# Сначала lockfiles -> лучший кэш
COPY dashboard/frontend/package.json dashboard/frontend/package-lock.json ./
RUN npm ci

COPY dashboard/frontend/index.html ./index.html
COPY dashboard/frontend/vite.config.js ./vite.config.js
COPY dashboard/frontend/src ./src

RUN npm run build

############################
# 2) Custom Caddy build (xcaddy + plugins)
############################
FROM caddy:${CADDY_VERSION}-builder AS caddy_builder
ENV GOTOOLCHAIN=go1.25.1

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    xcaddy build \
      --with github.com/mholt/caddy-l4@8e3b9724e26abc5f028fbce9948682bc62864804 \
      --with github.com/greenpau/caddy-security@v1.1.29 \
      --with github.com/mholt/caddy-ratelimit \
      --with github.com/darkweak/souin/plugins/caddy \
      --with github.com/caddyserver/cache-handler \
      --with github.com/greenpau/caddy-trace \
      --with github.com/grom11/caddy-logtail \
      --with github.com/lucaslorentz/caddy-docker-proxy/v2 \
      --with github.com/caddyserver/geoip2 \
      --with github.com/ss098/caddy-extauth \
      --with github.com/caddy-dns/cloudflare \
      --with github.com/gamalan/caddy-tlsredis \
      --with github.com/caddyserver/replace-response \
      --with github.com/caddyserver/json5-adapter \
      --with github.com/caddyserver/caddy-fs-s3 \
      --with github.com/caddyserver/s3storage \
      --with github.com/mholt/caddy-webdav

############################
# 3) Runtime (Python 3.14 + uv + backend + static + caddy)
############################
FROM python:${PYTHON_VERSION} AS runtime
WORKDIR /app

# uv (быстрый менеджер зависимостей)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Для максимального кеша: сначала только манифесты
COPY pyproject.toml uv.lock ./

# Ставим зависимости строго по lock (воспроизводимо + быстро)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Код приложения
COPY dashboard/app /app/app

# Статика фронта
COPY --from=frontend /frontend/dist /app/static

# Кастомный caddy
COPY --from=caddy_builder /usr/bin/caddy /usr/bin/caddy

ENV PYTHONUNBUFFERED=1

EXPOSE 8090
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]