.PHONY: up down logs logs-backend build migrate seed seed-history seed-all shell test lint dev-backend dev-frontend health backup restore certbot

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
