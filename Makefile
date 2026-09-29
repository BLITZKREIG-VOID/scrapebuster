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
	cd dashboard && npm run typecheck && npm run build

test-unit:
	PYTHONPATH=backend pytest backend/tests/unit/ -v

test-contract:
	PYTHONPATH=backend pytest backend/tests/contract/ -v

test-integration:
	PYTHONPATH=backend pytest backend/tests/integration/ -v

reset:
	python -c "from sb.store.db import reset_db; reset_db(); print('DB reset.')"
