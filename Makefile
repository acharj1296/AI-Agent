PYTHON := .venv/Scripts/python.exe
UV := uv

.PHONY: install dev run migrate test test-int lint format typecheck up down help

install: ## Create venv (Python 3.12 via uv) and install dev deps
	$(UV) venv --python 3.12 .venv
	$(UV) pip install --python .venv/Scripts/python.exe -e ".[dev]"

dev: ## Start local MongoDB, initialize indexes, and run the API
	docker compose -f deploy/environments/local/docker-compose.yaml up -d mongodb
	$(MAKE) migrate
	$(MAKE) run

run: ## Run the API with uvicorn (hot reload)
	$(PYTHON) -m uvicorn aiagent.api.app:app --reload --host $$(hostname 2>/dev/null || echo 127.0.0.1) --port 8000

migrate: ## Initialize MongoDB collections and indexes (idempotent)
	$(PYTHON) -m aiagent.db

# aliases to satisfy `make test-int`
test-int: test

test: ## Run the test suite
	$(PYTHON) -m pytest

lint: ## Lint with ruff
	$(PYTHON) -m ruff check src tests

format: ## Format with black + ruff
	$(UV) run --with black black src tests --skip-string-normalization
	$(PYTHON) -m ruff format src tests

typecheck: ## Type check with mypy
	$(PYTHON) -m mypy src

up: ## Start local MongoDB
	docker compose -f deploy/environments/local/docker-compose.yaml up -d

down: ## Stop local services
	docker compose -f deploy/environments/local/docker-compose.yaml down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
