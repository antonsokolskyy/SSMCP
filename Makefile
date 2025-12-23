.PHONY: help test test-cov check check-fix clean shell rebuild build start up down stop restart logs

SERVICE_NAME=ssmcp

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

build:  ## Build the Docker image
	docker compose up -d --build --force-recreate $(SERVICE_NAME)

rebuild: build ## Alias for build - Build the Docker image

up:  ## Start all services in detached mode
	docker compose up -d

start: up ## Alias for up - Start all services in detached mode

down:  ## Stop all services
	docker compose down

stop: down  ## Alias for down - Stop all services

restart:  ## Restart the MCP server service
	docker compose up -d --force-recreate $(SERVICE_NAME)

logs:  ## View logs from ssmcp service
	docker compose logs $(SERVICE_NAME) -f

.DEFAULT_GOAL := help
