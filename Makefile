.PHONY: setup up backend site dashboard test-unit test-contract test-integration e2e check preflight reset demo demo-step capture-golden restore-golden smoke

setup:
	python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	if [ -d dashboard ]; then cd dashboard && npm install; fi

backend:
	python -m uvicorn sb.main:app --app-dir backend --port 8000 --reload

site:
	if [ -d demo_site ]; then python -m uvicorn demo_site.app:app --port 8001 --reload; else echo "demo_site directory not present"; fi

dashboard:
	if [ -d dashboard ]; then cd dashboard && npm run dev; else echo "dashboard directory not present"; fi

up:
	@echo "Run backend, site, and dashboard in separate terminals or use a multiplexer."

check:
	python -m ruff check backend/sb/main.py backend/sb/contracts.py backend/sb/store backend/sb/edge backend/sb/api scripts/check_contracts.py scripts/export_schemas.py
	python -m pytest backend/tests/unit/ -q
	python -m pytest backend/tests/contract/ -q
	python scripts/check_ownership.py
	python scripts/check_contracts.py
	if [ -d dashboard ]; then cd dashboard && npm run typecheck && npm run build; fi

test-unit:
	PYTHONPATH=backend pytest backend/tests/unit/ -v

test-contract:
	PYTHONPATH=backend pytest backend/tests/contract/ -v

test-integration:
	PYTHONPATH=backend pytest backend/tests/integration/ -v

# Temporary DB-only reset. Arnav owns the full demo reset endpoint/runner.
reset:
	PYTHONPATH=backend python -c "from sb.store.db import reset_db; reset_db(); print('DB reset.')"
