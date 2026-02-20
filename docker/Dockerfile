# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.14-slim
ARG NODE_VERSION=20-alpine

############################
# 1) Frontend build (Vite)
############################
FROM node:${NODE_VERSION} AS frontend_builder
WORKDIR /frontend

COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci

COPY src/frontend/ ./
RUN npm run build

############################
# 2) Backend runtime
############################
FROM python:${PYTHON_VERSION} AS backend_runtime
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY src/backend/ /app/backend/

RUN mkdir -p /app/backend/static /app/backend/templates
COPY --from=frontend_builder /frontend/dist/ /app/backend/static/
COPY --from=frontend_builder /frontend/dist/index.html /app/backend/templates/index.html

RUN mkdir -p /data/caddy /data/cloudflare /data/settings /data/vpn

ENV PYTHONUNBUFFERED=1 \
    ROUTES_FILE=/data/caddy/routes.json \
    CADDYFILE_PATH=/data/caddy/Caddyfile \
    SETTINGS_JSON_FILE=/data/settings/app_settings.json \
    CLOUDFLARE_API_TOKEN_FILE=/data/cloudflare/api_token.txt \
    CLOUDFLARE_DEFAULT_SERVICE=http://172.17.0.1:80 \
    CADDY_RUNTIME_HTTP_PORT=80 \
    CADDY_RUNTIME_HTTPS_PORT=443 \
    CF_TUNNEL_DIR= \
    FEATURE_TUNNEL_ENABLED=true \
    FEATURE_VPN_ENABLED=true \
    VPN_DATA_DIR=/data/vpn \
    VPN_STATE_FILE=/data/vpn/state.json \
    DASHBOARD_PORT=8090

EXPOSE 8090
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8090"]
