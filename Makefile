.PHONY: help setup backend dashboard test test-unit test-contract test-integration check grep-gate preflight smoke reset-db clean

help:
	@echo "ScrapeBusters Pure Layer 3 Full Offense Makefile Targets:"
	@echo "  setup            Install backend and dashboard dependencies"
	@echo "  backend          Run ScrapeBusters backend edge server (:8000)"
	@echo "  dashboard        Run dashboard dev server (:5173) if present"
	@echo "  check            Run lint + grep-gate + ownership + contracts + unit + contract + integration + dashboard checks"
	@echo "  grep-gate        Verify zero forbidden tokens outside .git"
	@echo "  test             Run all test suites (unit, contract, integration)"
	@echo "  test-unit        Run unit test suite"
	@echo "  test-contract    Run contract test suite"
	@echo "  test-integration Run integration test suite"
	@echo "  preflight        Run stdlib preflight environment checks"
	@echo "  smoke            Run smoke checks against running services"
	@echo "  reset-db         Directly reset SQLite database tables"
	@echo "  clean            Remove temporary and build cache artifacts"

setup:
	python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	if [ -d dashboard ]; then cd dashboard && npm install; fi

backend:
	python -m uvicorn sb.main:app --app-dir backend --port 8000 --reload

dashboard:
	if [ -d dashboard ]; then cd dashboard && npm run dev; else echo "dashboard directory not present"; fi

grep-gate:
	python scripts/grep_gate.py .

check:
	python -m ruff check backend/sb/main.py backend/sb/contracts.py backend/sb/store backend/sb/edge backend/sb/api scripts/check_contracts.py scripts/export_schemas.py
	python scripts/grep_gate.py .
	python scripts/check_ownership.py
	python scripts/check_contracts.py
	PYTHONPATH=backend python -m pytest backend/tests/unit/ -q
	PYTHONPATH=backend python -m pytest backend/tests/contract/ -q
	PYTHONPATH=backend python -m pytest backend/tests/integration/ -q
	if [ -d dashboard ]; then cd dashboard && npm run typecheck && npm run build; fi

test: test-unit test-contract test-integration

test-unit:
	PYTHONPATH=backend python -m pytest backend/tests/unit/ -v

test-contract:
	PYTHONPATH=backend python -m pytest backend/tests/contract/ -v

test-integration:
	PYTHONPATH=backend python -m pytest backend/tests/integration/ -v

preflight:
	python scripts/preflight.py

smoke:
	bash scripts/smoke.sh

reset-db:
	PYTHONPATH=backend python -c "from sb.store.db import reset_db; reset_db(); print('DB reset.')"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
