"""The public control plane must win routing before the upstream catch-all."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient


@pytest.fixture
def runtime_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from sb.store import db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "api-runtime.db"))
    db.reset_db()

    from sb.edge.session import sessions

    sessions.reset()

    from sb import main
    from sb.api import demo as demo_api

    proxied_paths: list[str] = []

    async def fake_edge_handler(request):
        proxied_paths.append(request.url.path)
        return HTMLResponse(
            f"<html><body>Upstream sentinel: {request.url.path}</body></html>"
        )

    monkeypatch.setattr(main, "handle", fake_edge_handler)
    if hasattr(demo_api, "reset_demo"):
        monkeypatch.setattr(
            demo_api,
            "reset_demo",
            lambda: {"ok": True, "run_id": "RUN-routing-test", "checks": []},
        )
    if hasattr(demo_api, "runner"):
        monkeypatch.setattr(
            demo_api.runner,
            "start",
            lambda step=None: {
                "run_id": "RUN-routing-test",
                "phase": "RUNNING",
                "mode": "live",
                "steps": [],
            },
        )
        monkeypatch.setattr(
            demo_api.runner,
            "get_status",
            lambda: {
                "run_id": "RUN-routing-test",
                "phase": "READY",
                "mode": "live",
                "steps": [],
            },
        )
    if hasattr(demo_api, "golden"):
        monkeypatch.setattr(
            demo_api.golden,
            "restore",
            lambda: {
                "run_id": "RUN-routing-test",
                "phase": "COMPLETE",
                "mode": "golden",
                "steps": [],
            },
        )

    with TestClient(main.app) as client:
        yield client, proxied_paths, main.app


def _assert_json(response, expected_status: int = 200) -> None:
    assert response.status_code == expected_status, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert "Upstream sentinel" not in response.text


def test_control_endpoints_resolve_without_entering_edge(runtime_client):
    client, proxied_paths, _ = runtime_client
    requests = [
        client.get("/api/v1/health"),
        client.get("/api/v1/overview"),
        client.get("/api/v1/traffic/events"),
        client.get("/api/v1/sessions"),
        client.get("/api/v1/canaries"),
        client.get("/api/v1/datasets"),
        client.get("/api/v1/probes"),
        client.get("/api/v1/cases"),
    ]

    for response in requests:
        _assert_json(response)

    # Unregistered /api/v1 origin paths forward to upstream and mutate per finding (3)
    resp = client.get("/api/v1/not-a-control-route")
    assert resp.status_code == 200
    assert proxied_paths == ["/api/v1/not-a-control-route"]


def test_provenance_endpoint_families_resolve_as_api(runtime_client, tmp_path: Path):
    client, proxied_paths, _ = runtime_client
    requests = [
        (client.get("/api/v1/canaries/NO-SUCH-CANARY"), 404),
        (
            client.post(
                "/api/v1/datasets/ingest",
                json={"path": str(tmp_path / "missing.jsonl"), "role": "target"},
            ),
            404,
        ),
        (client.post("/api/v1/probes/run", json={}), 409),
        (client.get("/api/v1/probes/NO-SUCH-PROBE"), 404),
        (client.get("/api/v1/cases/NO-SUCH-CASE"), 404),
        (client.get("/api/v1/cases/NO-SUCH-CASE/evidence"), 404),
        (client.post("/api/v1/cases/NO-SUCH-CASE/verify"), 404),
    ]

    for response, expected_status in requests:
        _assert_json(response, expected_status)

    assert proxied_paths == []


def test_demo_routes_resolve_at_their_single_application_prefix(runtime_client):
    client, proxied_paths, _ = runtime_client

    _assert_json(client.get("/api/v1/demo/status"))
    _assert_json(client.post("/api/v1/demo/reset"))
    # Unregistered subpaths forward to upstream per finding (3)
    proxied_paths.clear()
    resp = client.get("/api/v1/api/v1/demo/status")
    assert resp.status_code == 200
    assert proxied_paths == ["/api/v1/api/v1/demo/status"]


def test_favicon_keeps_route_surface(runtime_client):
    client, proxied_paths, _ = runtime_client

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert proxied_paths == ["/favicon.ico"]


def test_unmatched_site_paths_reach_edge_and_control_routes_precede_catch_all(
    runtime_client,
):
    client, proxied_paths, app = runtime_client

    response = client.get("/catalog/item/42")
    assert response.status_code == 200
    assert "Upstream sentinel" in response.text
    assert proxied_paths == ["/catalog/item/42"]

    paths = [getattr(route, "path", None) for route in app.routes]
    catch_all_index = next(
        index for index, route in enumerate(app.routes)
        if getattr(route, "name", None) == "catch_all"
    )
    # Never broad /api exemption; known routes precede catch-all
    assert "/api/v1/{path:path}" not in paths

    required = {
        "/api/v1/health",
        "/api/v1/overview",
        "/api/v1/traffic/events",
        "/api/v1/sessions",
        "/api/v1/canaries",
        "/api/v1/datasets",
        "/api/v1/probes",
        "/api/v1/cases",
        "/api/v1/demo/status",
    }
    openapi_paths = app.openapi()["paths"]
    assert required <= set(openapi_paths)
