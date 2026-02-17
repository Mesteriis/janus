COMPOSE = docker compose -f docker-compose.yaml -f docker-compose.override.yaml

.PHONY: build build-caddy build-dashboard up down logs restart test-backend test-frontend clean

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
