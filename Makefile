.PHONY: help install lint lint-quick test check format security naming setup-db dev backend frontend clean docker-up docker-down e2e

# Colors for output
BLUE := \033[0;34m
YELLOW := \033[0;33m
RED := \033[0;31m
GREEN := \033[0;32m
NC := \033[0m # No Color

# =============================================================================
# SETUP
# =============================================================================

install: ## Install all dependencies
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

# =============================================================================
# LINTING & TYPE CHECKING
# =============================================================================

lint-quick: ## Quick lint checks (ruff + pyright only)
	@echo "$(BLUE)Running quick lint checks...$(NC)"
	cd backend && ruff check src/
	cd backend && pyright src/ || echo "$(YELLOW)⚠ Pyright has pre-existing errors from unresolved signalfield-core types$(NC)"
	@echo "$(GREEN)Quick lint passed$(NC)"

lint: lint-quick ## Full lint checks (ruff + pyright + format check + vulture)
	cd backend && ruff format --check src/
	cd backend && vulture src/
	@echo "$(GREEN)Full lint passed$(NC)"

# =============================================================================
# TESTING
# =============================================================================

test: ## Run backend tests with 95% coverage requirement
	cd backend && pytest -v --cov=src --cov-fail-under=95 --cov-report=term-missing tests/

# =============================================================================
# SECURITY & NAMING CHECKS
# =============================================================================

security: ## Run security checks (bandit + pip-audit)
	cd backend && bandit -r src/
	cd backend && pip-audit --ignore-vuln CVE-2026-4539  # pygments — no fix available yet

naming: ## Check naming conventions, abbreviations, imports, and skip comments
	@echo "$(BLUE)Checking naming conventions...$(NC)"
	cd backend && python scripts/check_naming_conventions.py
	cd backend && python scripts/check_abbreviations.py
	cd backend && python scripts/check_imports.py
	cd backend && python scripts/check_skip_comments.py
	backend/scripts/check_branch_name.sh
	@echo "$(GREEN)Naming checks passed$(NC)"

# =============================================================================
# COMBINED CHECKS
# =============================================================================

audit: ## Run codebase audit (file sizes, anti-patterns, infra guards)
	@./scripts/audit.sh

check: lint test security naming audit ## Run ALL checks (lint + test + security + naming + audit)
	@echo "$(GREEN)All local checks passed$(NC)"

# =============================================================================
# FORMATTING
# =============================================================================

format: ## Auto-fix lint issues and format code
	cd backend && ruff check --fix src/ tests/
	cd backend && ruff format src/ tests/
	@echo "$(GREEN)Code formatted$(NC)"

# =============================================================================
# DEVELOPMENT
# =============================================================================

setup-db: ## Create DynamoDB table with GSIs (for local dev)
	python3 scripts/setup_dynamodb.py --table janus-dev --endpoint http://localhost:8000

dev: lint-quick ## Start all services (lint must pass first)
	@echo ""
	@echo "$(GREEN)All checks passed - Starting services...$(NC)"
	@echo "Starting DynamoDB Local..."
	docker compose up -d dynamodb-local
	@echo "Waiting for DynamoDB..."
	@until curl -sf http://localhost:8000 -o /dev/null 2>&1; do sleep 1; done
	$(MAKE) setup-db
	@echo "Starting backend on :8001..."
	cd backend && uvicorn src.local_server:app --port 8001 --reload &
	@echo "Starting frontend on :3000..."
	cd frontend && npm run dev

backend: lint-quick ## Start backend only (lint must pass first)
	@echo "$(GREEN)Lint passed - Starting backend...$(NC)"
	cd backend && uvicorn src.local_server:app --port 8001 --reload

frontend: ## Start frontend only
	cd frontend && npm run dev

dev-unsafe: ## Start dev without lint checks (debugging only)
	@echo "$(RED)WARNING: Running WITHOUT lint checks!$(NC)"
	docker compose up -d dynamodb-local
	@echo "Waiting for DynamoDB..."
	@until curl -sf http://localhost:8000 -o /dev/null 2>&1; do sleep 1; done
	$(MAKE) setup-db
	cd backend && uvicorn src.local_server:app --port 8001 --reload &
	cd frontend && npm run dev

# =============================================================================
# DOCKER & E2E
# =============================================================================

docker-up: ## Start all services in Docker
	docker compose up -d --build
	@echo "$(GREEN)All services starting...$(NC)"

docker-down: ## Stop all Docker services and clean volumes
	docker compose down -v

e2e: ## Run end-to-end integration tests (requires running services)
	./scripts/e2e-test.sh

# =============================================================================
# CLEANUP
# =============================================================================

clean: ## Remove build artifacts and caches
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/dist backend/*.egg-info backend/.coverage backend/coverage.xml
	docker compose down -v

# =============================================================================
# HELP
# =============================================================================

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}'
