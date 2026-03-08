.PHONY: up down logs logs-backend build migrate seed seed-history seed-all shell test test-cov test-unit test-integration test-e2e mutmut-run mutmut-results lint dev-backend dev-frontend health backup restore certbot

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m scripts.seed_sp500

seed-history:
	docker compose exec backend python -m scripts.seed_historical_data

seed-all:
	docker compose exec backend python -m scripts.seed_sp500
	docker compose exec backend python -m scripts.seed_historical_data

shell:
	docker compose exec backend bash

test:
	cd backend && python -m pytest tests/ -v

test-cov:
	cd backend && python -m pytest tests/ -v --cov --cov-report=html --cov-report=term-missing

test-unit:
	cd backend && python -m pytest tests/ -v -m "not integration"

test-integration:
	cd backend && python -m pytest tests/integration/ -v -m integration

test-e2e:
	cd frontend && npx playwright test

mutmut-run:
	cd backend && python -m mutmut run --paths-to-mutate=worker/utils/technical_indicators.py
	cd backend && python -m mutmut run --paths-to-mutate=worker/utils/backtester/metrics.py
	cd backend && python -m mutmut run --paths-to-mutate=worker/utils/backtester/engine.py
	cd backend && python -m mutmut run --paths-to-mutate=worker/tasks/signals/component_scores.py

mutmut-results:
	cd backend && python -m mutmut results

lint:
	cd backend && ruff check . && ruff format --check .

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

health:
	curl -s localhost/api/health?detail=true | python3 -m json.tool

backup:
	bash scripts/backup.sh

restore:
	bash scripts/restore.sh $(FILE)

certbot:
	docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d $(DOMAIN)
