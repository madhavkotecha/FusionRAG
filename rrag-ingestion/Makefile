.PHONY: dev test build up down lint

dev:
	uvicorn rrag_ingestion.main:app --host 0.0.0.0 --port 8001 --reload

worker:
	rq worker --with-scheduler -u redis://localhost:6381/1

test:
	pytest tests/ -v --cov=rrag_ingestion

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

install:
	pip install -e ".[all,dev]"
