PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
COMPOSE ?= docker-compose

.PHONY: help install dev-setup test clean lint format migrate build up down

help: ## Show this help message
	@echo "KAISON AI - Developer Commands"
	@echo "================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install: ## Install Python dependencies
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

dev-setup: install ## Full development setup
	cp -n .env.example .env || true
	$(COMPOSE) up -d postgres redis
	sleep 5
	alembic upgrade head

test: ## Run all tests
	$(PYTHON) -m pytest -v

clean: ## Clean Python cache, AI assistant directories, and artifacts
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache htmlcov .mypy_cache .ruff_cache build/ dist/ *.egg-info
	@echo "Removing AI assistant directories (.claude, .codex)..."
	rm -rf .claude/ .codex/
	@echo "Cache and AI directories cleaned."

lint: ## Run linting
	ruff check apps/backend/src tests scripts

format: ## Auto-format code
	black apps/backend/src tests scripts
	isort apps/backend/src tests scripts

migrate: ## Run database migrations
	alembic upgrade head

build: ## Build Docker images
	$(COMPOSE) build

up: ## Start all services
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

logs: ## Tail logs
	$(COMPOSE) logs -f
