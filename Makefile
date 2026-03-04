.PHONY: up down logs migrate seed shell test lint

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m scripts.seed_sp500

shell:
	docker compose exec backend bash

test:
	cd backend && python -m pytest tests/ -v

lint:
	cd backend && ruff check . && ruff format --check .

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev
