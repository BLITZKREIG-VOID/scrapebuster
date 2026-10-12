"""Unit tests for Phase 4 Callback Engine endpoints (PRD M4 / FR-4.1, FR-4.2)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sb.canary.registry import bind_session_canary
from sb.main import app
from sb.store.db import reset_db


@pytest.fixture(autouse=True)
def clean_state():
    reset_db()
    yield
    reset_db()


def test_image_callback_via_query_params():
    """Test /api/v1/callbacks/image.gif accepts query parameter 'c' and returns 1x1 GIF."""
    client = TestClient(app)
    binding = bind_session_canary("sess-cb-1", vector="BEACON", value="test_token_123")

    response = client.get(f"/api/v1/callbacks/image.gif?c={binding.canary_id}&t=test_token_123")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/gif"
    assert response.content.startswith(b"GIF89a")
    assert "x-callback-id" in response.headers


def test_root_beacon_gif_via_query_params():
    """Test /beacon.gif route matching injected HTML src returns 1x1 GIF."""
    client = TestClient(app)
    binding = bind_session_canary("sess-cb-2", vector="BEACON", value="val_root_beacon")

    response = client.get(f"/beacon.gif?c={binding.canary_id}&t=val_root_beacon")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/gif"
    assert response.content.startswith(b"GIF89a")


def test_image_callback_missing_canary_returns_400():
    """Test request without 'c' parameter returns 400."""
    client = TestClient(app)
    response = client.get("/beacon.gif")
    assert response.status_code == 400


def test_honeykey_interception_endpoint():
    """Test POST /api/v1/callbacks/honeykey captures submitted key."""
    client = TestClient(app)
    payload = {
        "key_id": "hk-secret-key-1",
        "key_value": "secret_extracted_token",
        "source_url": "http://127.0.0.1:8000/products",
        "session_id": "sess-hk-1",
    }
    response = client.post("/api/v1/callbacks/honeykey", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "captured"
    assert data["callback_id"].startswith("CBK-")
