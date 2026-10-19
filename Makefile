.PHONY: backend backend-local web-start web-stop web-dev web-build test test-api test-web test-e2e

backend:
	docker compose up --build -d

backend-local:
	.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

web-start:
	./scripts/start-web.sh

web-stop:
	./scripts/stop-web.sh

web-dev:
	npm --prefix web run dev

web-build:
	npm --prefix web run build

test: test-api test-web

test-api:
	PYTHONPATH=backend .venv/bin/pytest backend/tests -q

test-web:
	npm --prefix web test

test-e2e:
	npm --prefix web run test:e2e
