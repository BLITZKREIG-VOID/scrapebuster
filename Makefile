.PHONY: setup up backend site dashboard test-unit test-contract test-integration e2e check preflight reset demo demo-step capture-golden restore-golden smoke

setup:
	pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	cd dashboard && npm install

backend:
	uvicorn sb.main:app --port 8000 --reload

site:
	uvicorn demo_site.app:app --port 8001 --reload

dashboard:
	cd dashboard && npm run dev

up:
	# P1: proper concurrent runner, for now this is just a placeholder
	@echo "Run backend, site, and dashboard in separate terminals or use a multiplexer."

check:
	ruff check backend/
	pytest backend/tests/unit/
	pytest backend/tests/contract/
	python scripts/check_ownership.py
	python scripts/check_contracts.py
	cd dashboard && npm run typecheck && npm run build

test-unit:
	PYTHONPATH=backend pytest backend/tests/unit/ -v

test-contract:
	PYTHONPATH=backend pytest backend/tests/contract/ -v

test-integration:
	PYTHONPATH=backend pytest backend/tests/integration/ -v

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
	SB_EDGE_URL=$(EDGE) PYTHONPATH=backend pytest backend/tests/e2e/ -v

demo:
	cd backend && python -m sb.demo.runner --base $(EDGE)

demo-step:
	cd backend && python -m sb.demo.runner --base $(EDGE) --step-mode

# Only from a live run where all 7 steps passed (golden.py refuses otherwise).
capture-golden:
	cd backend && python -m sb.demo.golden capture

restore-golden:
	python scripts/demo_api.py $(EDGE) restore-golden
