.PHONY: help dev up down logs traefik-logs migrate test test-watch build clean seed

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Development ──────────────────────────────────────────────

dev: ## Start infra + run auth server in dev mode (hot reload)
	docker compose up -d postgres redis
	@echo "Waiting for services..."
	@sleep 2
	npm run dev

up: ## Start all services (infra + auth server) via docker compose
	docker compose up -d --build

down: ## Stop all services
	docker compose down

logs: ## Tail auth server logs
	docker compose logs -f auth-server

traefik-logs: ## Tail Traefik gateway logs
	docker compose logs -f traefik

ps: ## Show running services
	docker compose ps

# ── Database ─────────────────────────────────────────────────

migrate: ## Run Drizzle migrations against local DB
	docker compose up -d postgres
	@sleep 2
	npx drizzle-kit migrate

db-generate: ## Generate new migration from schema changes
	npx drizzle-kit generate

db-studio: ## Open Drizzle Studio (DB GUI)
	npx drizzle-kit studio

db-create-test: ## Create test database
	docker compose exec postgres psql -U rrag -c "CREATE DATABASE rrag_test" 2>/dev/null || true

# ── Testing ──────────────────────────────────────────────────

test: db-create-test ## Run all tests (starts DB if needed)
	docker compose up -d postgres redis
	@sleep 2
	@docker compose exec -T postgres psql -U rrag -d rrag_test -c "SELECT 1 FROM organizations LIMIT 0" 2>/dev/null || \
		docker compose exec -T postgres psql -U rrag -d rrag_test < drizzle/migrations/0000_long_miss_america.sql
	npm test

test-watch: ## Run tests in watch mode
	npm run test:watch

test-coverage: ## Run tests with coverage report
	npm run test:coverage

# ── Build ────────────────────────────────────────────────────

build: ## Compile TypeScript
	npm run build

typecheck: ## Run type checker (no emit)
	npm run typecheck

docker-build: ## Build Docker image
	docker build -t rrag-auth-server .

# ── Cleanup ──────────────────────────────────────────────────

clean: ## Remove build artifacts and volumes
	rm -rf dist coverage node_modules/.cache

nuke: ## Full reset: stop services, remove volumes, clean
	docker compose down -v
	rm -rf dist coverage
