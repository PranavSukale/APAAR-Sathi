.PHONY: up down seed test demo api web install fmt

up:
	docker compose up -d
	python backend/scripts/wait_for_db.py
	python -m backend.app.core.dbinit

down:
	docker compose down

install:
	python -m pip install -r backend/requirements.txt

seed:
	python -m scripts.seed

test:
	python -m pytest backend/tests -q

demo:
	python -m scripts.demo

api:
	python -m uvicorn backend.app.main:app --reload --port 8000

web:
	cd frontend && npm run dev
