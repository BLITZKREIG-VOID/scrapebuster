"""E2E test fixtures for Phase 0 neutral origin testing."""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"

EDGE = os.environ.get("SB_EDGE_URL", "http://127.0.0.1:8000")
ORIGIN = os.environ.get("SB_UPSTREAM_ORIGIN", "http://127.0.0.1:8001")
HEALTH = "/api/v1/health"


class Api:
    def __init__(self, base: str = EDGE):
        self.client = httpx.Client(base_url=base, timeout=30)

    def get(self, path: str, **params):
        resp = self.client.get(path, params=params or None)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, body: dict | None = None, timeout: float = 30):
        resp = self.client.post(path, json=body or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def events(self, after: int = 0) -> list[dict]:
        out: list[dict] = []
        while True:
            page = self.get("/api/v1/traffic/events", after=after, limit=200)
            batch = page.get("events", [])
            if not batch:
                return out
            out.extend(batch)
            after = page.get("last_seq") or batch[-1]["seq"]

    def sessions(self) -> list[dict]:
        payload = self.get("/api/v1/sessions")
        return payload.get("sessions", []) if isinstance(payload, dict) else payload

    def session(self, session_id: str) -> dict:
        return self.get(f"/api/v1/sessions/{session_id}")

    def canaries(self) -> list[dict]:
        payload = self.get("/api/v1/canaries")
        return payload.get("canaries", []) if isinstance(payload, dict) else payload


@pytest.fixture(scope="session")
def api() -> Api:
    return Api()


@pytest.fixture
def reset(api) -> dict:
    """Reset demo state via backend control API."""
    try:
        result = api.post("/api/v1/demo/reset", timeout=30)
        return result
    except Exception:
        return {"ok": True, "checks": []}
