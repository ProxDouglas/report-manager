PYTHON_BIN ?= .venv/bin/python
PIP_BIN ?= .venv/bin/pip

.PHONY: install backend-install frontend-install dev dev-up dev-down migrate migrate-check test frontend-test frontend-e2e lint typecheck build security sandbox-check

install: backend-install frontend-install

backend-install:
	python3 -m venv .venv
	$(PIP_BIN) install --upgrade pip
	$(PIP_BIN) install -r backend/requirements-dev.txt

frontend-install:
	cd frontend && npm ci

dev:
	@echo "Use 'make dev-up' para iniciar API, worker, frontend e PostgreSQL."

dev-up:
	docker compose --env-file .env -f infra/docker-compose.yml up --build

dev-down:
	docker compose --env-file .env -f infra/docker-compose.yml down

migrate:
	$(PYTHON_BIN) -m alembic -c alembic.ini upgrade head

migrate-check:
	$(PYTHON_BIN) -m alembic -c alembic.ini check

test:
	$(PYTHON_BIN) -m pytest backend/tests
	cd frontend && npm test -- --run

frontend-test:
	cd frontend && npm test -- --run

frontend-e2e:
	cd frontend && npm run test:e2e

lint:
	$(PYTHON_BIN) -m ruff check backend
	cd frontend && npm run lint

typecheck:
	cd backend && ../$(PYTHON_BIN) -m mypy app worker
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

security:
	$(PYTHON_BIN) -m pip_audit -r backend/requirements.txt
	cd frontend && npm audit --audit-level=high

sandbox-check:
	scripts/check-sandbox.sh
