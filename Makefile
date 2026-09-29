.PHONY: help setup up backend site dashboard test-unit test-contract test-integration e2e check preflight reset demo demo-step capture-golden restore-golden smoke reset-db

help:
	@echo "ScapeBusters Makefile Targets:"
	@echo "  setup            Install backend and dashboard dependencies"
	@echo "  up               Instructions for starting all services"
	@echo "  backend          Run ScapeBusters backend edge server (:8000)"
	@echo "  site             Run local test fixture site (:8001) if present"
	@echo "  dashboard        Run dashboard dev server (:5173) if present"
	@echo "  check            Run linters, unit/contract tests, ownership & contract checks"
	@echo "  test-unit        Run unit test suite"
	@echo "  test-contract    Run contract test suite"
	@echo "  test-integration Run integration test suite"
	@echo "  e2e              Run end-to-end test suite against EDGE (default: http://127.0.0.1:8000)"
	@echo "  preflight        Run stdlib preflight environment and dataset checks"
	@echo "  reset            Reset demo state via running backend (POST /api/v1/demo/reset)"
	@echo "  demo             Run 7-step automated demo runner against EDGE"
	@echo "  demo-step        Run interactive step-by-step demo runner against EDGE"
	@echo "  capture-golden   Capture golden run from a fully passed demo run"
	@echo "  restore-golden   Restore golden demo run state (POST /api/v1/demo/restore-golden)"
	@echo "  smoke            Run smoke checks against running edge and backend"
	@echo "  reset-db         Directly reset SQLite database tables"

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
	PYTHONPATH=backend python -m pytest backend/tests/unit/ -q
	PYTHONPATH=backend python -m pytest backend/tests/contract/ -q
	python scripts/check_ownership.py
	python scripts/check_contracts.py
	if [ -d dashboard ]; then cd dashboard && npm run typecheck && npm run build; fi

test-unit:
	PYTHONPATH=backend python -m pytest backend/tests/unit/ -v

test-contract:
	PYTHONPATH=backend python -m pytest backend/tests/contract/ -v

test-integration:
	PYTHONPATH=backend python -m pytest backend/tests/integration/ -v

# ── Demo targets (Arnav, plan §20/§21, R-08). Every target talks to the local edge only.
EDGE ?= http://127.0.0.1:8000

# §21 demo reset via the running backend (409 while a run holds the lock; non-zero on any failed check).
reset:
	python scripts/demo_api.py $(EDGE) reset

preflight:
	python scripts/preflight.py

smoke:
	bash scripts/smoke.sh

e2e:
	SB_EDGE_URL=$(EDGE) PYTHONPATH=backend python -m pytest backend/tests/e2e/ -v

demo:
	cd backend && python -m sb.demo.runner --base $(EDGE)

demo-step:
	cd backend && python -m sb.demo.runner --base $(EDGE) --step-mode

# Only from a live run where all 7 steps passed (golden.py refuses otherwise).
capture-golden:
	cd backend && python -m sb.demo.golden capture

restore-golden:
	python scripts/demo_api.py $(EDGE) restore-golden

# Direct DB-only reset helper
reset-db:
	PYTHONPATH=backend python -c "from sb.store.db import reset_db; reset_db(); print('DB reset.')"

