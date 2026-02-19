COMPOSE = docker compose -f docker-compose.yaml -f docker-compose.override.yaml

.PHONY: build build-caddy build-dashboard up down logs restart test-backend test-frontend clean ui-local

build: ## Build all images
	$(COMPOSE) build

build-caddy: ## Build only caddy image
	$(COMPOSE) build caddy

build-dashboard: ## Build only dashboard image
	$(COMPOSE) build dashboard

up: ## Start stack in background
	$(COMPOSE) up -d

down: ## Stop stack
	$(COMPOSE) down

logs: ## Tail all logs
	$(COMPOSE) logs -f

restart: down up ## Restart stack

test-backend: ## Run backend tests
	cd dashboard && pytest

test-frontend: ## Build frontend (lint/tests can be added later)
	cd dashboard/frontend && npm run build

clean: ## Remove build artifacts
	$(COMPOSE) down -v --rmi local

ui-local: ## Run WebUI locally at http://127.0.0.1:8091 (bypass Docker port forwarding)
	cd src/frontend && npm ci && npm run build
	rm -rf src/backend/static src/backend/templates
	mkdir -p src/backend/static src/backend/templates
	cp -R src/frontend/dist/. src/backend/static/
	cp src/frontend/dist/index.html src/backend/templates/index.html
	uv run --env-file .env -- python -m uvicorn backend.main:app --host 127.0.0.1 --port 8091 --app-dir src
