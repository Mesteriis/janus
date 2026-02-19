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

ENV PYTHONUNBUFFERED=1

EXPOSE 8090
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8090"]
