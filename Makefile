.PHONY: help test test-cov check check-fix clean shell rebuild build start up down stop restart logs

SERVICE_NAME=ssmcp
UI_SERVICE_NAME=ssmcp-ui

# Detect which compose file(s) to check by inspecting .env
COMPOSE_FILES := $(shell [ -f .env ] && grep "^COMPOSE_FILE=" .env | cut -d= -f2 | tr ':' ' ' || echo "docker-compose.yml")
ifeq ($(COMPOSE_FILES),)
	COMPOSE_FILES := docker-compose.yml
endif

# Detect if UI service is enabled (uncommented in any relevant compose file)
UI_ENABLED := $(shell for file in $(COMPOSE_FILES); do \
	if [ -f "$$file" ] && grep -q "^[[:space:]]*$(UI_SERVICE_NAME):" "$$file"; then \
		echo "true"; \
		exit 0; \
	fi; \
done; echo "false")

# Build list of services to manage
ifeq ($(UI_ENABLED),true)
	SERVICES := $(SERVICE_NAME) $(UI_SERVICE_NAME)
else
	SERVICES := $(SERVICE_NAME)
endif

help:  ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

test:  ## Run tests with coverage (inside container)
	@if [ -z "$$(docker compose ps -q $(SERVICE_NAME))" ]; then \
		echo "Container not running. Starting it..."; \
		docker compose up $(SERVICE_NAME) -d; \
	fi
	@BUILD_ENV=$$(docker compose exec -T $(SERVICE_NAME) printenv BUILD_ENV 2>/dev/null | tr -d '\r'); \
	if [ "$$BUILD_ENV" = "production" ]; then \
		echo "ERROR: Test files and dependencies are excluded from production image. Use development environment instead."; \
		exit 1; \
	fi
	docker compose exec $(SERVICE_NAME) uv run --group test pytest

test-cov:  ## Run tests with coverage report (HTML output in htmlcov/)
	@if [ -z "$$(docker compose ps -q $(SERVICE_NAME))" ]; then \
		echo "Container not running. Starting it..."; \
		docker compose up $(SERVICE_NAME) -d; \
	fi
	@BUILD_ENV=$$(docker compose exec -T $(SERVICE_NAME) printenv BUILD_ENV 2>/dev/null | tr -d '\r'); \
	if [ "$$BUILD_ENV" = "production" ]; then \
		echo "ERROR: Test files and dependencies are excluded from production image. Use development environment instead."; \
		exit 1; \
	fi
	docker compose exec $(SERVICE_NAME) uv run --group test pytest --cov-report=html:htmlcov --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

check:  ## Check code (lint + type-check) (inside container)
	@if [ -z "$$(docker compose ps -q $(SERVICE_NAME))" ]; then \
		echo "Container not running. Starting it..."; \
		docker compose up $(SERVICE_NAME) -d; \
	fi
	docker compose exec $(SERVICE_NAME) uv run --group dev ruff check .
	docker compose exec $(SERVICE_NAME) uv run --group dev --group test mypy .

check-fix:  ## Fix Ruff errors (inside container)
	@if [ -z "$$(docker compose ps -q $(SERVICE_NAME))" ]; then \
		echo "Container not running. Starting it..."; \
		docker compose up $(SERVICE_NAME) -d; \
	fi
	docker compose exec $(SERVICE_NAME) uv run --group dev ruff check . --fix

clean:  ## Clean generated files
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage .coverage.*
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

shell:  ## Open a shell in the container
	docker compose exec $(SERVICE_NAME) bash

build:  ## Build and start services (includes UI if enabled)
	@echo "Building services: $(SERVICES)"
	docker compose up -d --build --force-recreate $(SERVICES)

rebuild: build ## Alias for build - Build and start services

up:  ## Start all services in detached mode
	docker compose up -d

start: up ## Alias for up - Start all services in detached mode

down:  ## Stop all services
	docker compose down

stop: down  ## Alias for down - Stop all services

restart:  ## Restart services (includes UI if enabled)
	@echo "Restarting services: $(SERVICES)"
	docker compose up -d --force-recreate $(SERVICES)

logs:  ## View logs from services (includes UI if enabled)
	@echo "Showing logs for: $(SERVICES)"
	docker compose logs $(SERVICES) -f

.DEFAULT_GOAL := help
