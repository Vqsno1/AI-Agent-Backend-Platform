.PHONY: install test lint migrate api worker up down
install:
	uv sync --frozen
migrate:
	uv run alembic upgrade head
api:
	uv run uvicorn app.main:app --reload
worker:
	uv run celery -A app.workers.worker:celery worker --loglevel=info --concurrency=2
test:
	uv run pytest -q
lint:
	uv run ruff check .
	uv run ruff format --check .
up:
	docker compose up --build -d
down:
	docker compose down
