.PHONY: up up-detach down down-volumes build rebuild migrate migrate-local seed demo \
        test test-local test-all test-policy test-simulator test-agent test-redteam \
        test-integration test-backend test-frontend lint lint-fix format typecheck \
        security clean help

# ── Local dev ──────────────────────────────────────────────────────────────────
up:
	docker compose up --build

up-detach:
	docker compose up --build -d

down:
	docker compose down

down-volumes:
	docker compose down -v

build:
	docker compose build

rebuild:
	docker compose build --no-cache

logs-backend:
	docker compose logs backend -f

logs-frontend:
	docker compose logs frontend -f

logs:
	docker compose logs -f

# ── Database ───────────────────────────────────────────────────────────────────
migrate:
	docker compose exec -w /app backend alembic -c backend/alembic.ini upgrade head

migrate-local:
	cd backend && alembic upgrade head

migrate-down:
	docker compose exec -w /app backend alembic -c backend/alembic.ini downgrade -1

# ── Seeding ────────────────────────────────────────────────────────────────────
seed:
	docker compose exec -w /app backend python -c \
	  "import sys; sys.path.insert(0,'/app/backend'); sys.path.insert(0,'/app'); import asyncio; from database.seed.seed_demo import seed; asyncio.run(seed())"

seed-local:
	python -m database.seed.seed_demo

demo: migrate seed
	@echo ""
	@echo "  RevenueRescue AI demo is ready."
	@echo "  Frontend:  http://localhost:3000"
	@echo "  API docs:  http://localhost:8000/docs"
	@echo "  Health:    http://localhost:8000/health"
	@echo ""

demo-reset:
	docker compose exec -w /app backend python -c \
	  "import sys; sys.path.insert(0,'/app/backend'); sys.path.insert(0,'/app'); import asyncio; from database.seed.seed_demo import seed; asyncio.run(seed())"

# ── Tests (local — no Docker needed) ─────────────────────────────────────────
test-local:
	python -m pytest policies/tests/ simulator/tests/ agents/tests/ \
	  tests/redteam/ tests/integration/ backend/tests/unit/ backend/tests/integration/ \
	  -v --tb=short

test-policy:
	python -m pytest policies/tests/ -v

test-simulator:
	python -m pytest simulator/tests/ -v

test-agent:
	python -m pytest agents/tests/ -v

test-redteam:
	python -m pytest tests/redteam/ -v

test-integration:
	python -m pytest tests/integration/ -v

test-backend-unit:
	python -m pytest backend/tests/ -v

# ── Tests (Docker) ─────────────────────────────────────────────────────────────
test:
	docker compose exec -w /app backend python -m pytest \
	  policies/tests/ simulator/tests/ agents/tests/ \
	  tests/redteam/ tests/integration/ backend/tests/ \
	  -v --tb=short

test-frontend:
	cd frontend && npm run test -- --run

test-all: test-local test-frontend

# ── Code quality ───────────────────────────────────────────────────────────────
lint:
	ruff check .
	cd frontend && npm run lint

lint-fix:
	ruff check . --fix

format:
	ruff format .

typecheck:
	mypy backend/app agents policies simulator --ignore-missing-imports
	cd frontend && npx tsc --noEmit

security:
	bandit -r backend/app agents policies simulator -x tests

# ── Clean ──────────────────────────────────────────────────────────────────────
clean:
	docker compose down -v
	python -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
	python -c "import shutil,pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if p.exists()]"

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  RevenueRescue AI — Development Commands"
	@echo "  ════════════════════════════════════════"
	@echo ""
	@echo "  Docker:"
	@echo "    make up              Start all 5 services (postgres, redis, backend, worker, frontend)"
	@echo "    make down            Stop all services"
	@echo "    make down-volumes    Stop and wipe all data volumes"
	@echo "    make rebuild         Force rebuild all Docker images"
	@echo "    make logs            Stream all container logs"
	@echo ""
	@echo "  Database:"
	@echo "    make migrate         Run Alembic migrations (Docker)"
	@echo "    make migrate-local   Run Alembic migrations (local)"
	@echo ""
	@echo "  Demo:"
	@echo "    make demo            Migrate + seed demo dataset"
	@echo "    make demo-reset      Re-seed demo data (wipes existing demo cases)"
	@echo ""
	@echo "  Tests (local — no Docker):"
	@echo "    make test-local      Full Python test suite (130 tests)"
	@echo "    make test-policy     Policy engine only (31 tests)"
	@echo "    make test-redteam    Red-team safety tests (25 tests)"
	@echo "    make test-agent      LangGraph agent tests (20 tests)"
	@echo ""
	@echo "  Quality:"
	@echo "    make lint            Ruff + ESLint"
	@echo "    make format          Ruff format"
	@echo "    make typecheck       MyPy + tsc"
	@echo "    make security        Bandit static analysis"
	@echo ""
