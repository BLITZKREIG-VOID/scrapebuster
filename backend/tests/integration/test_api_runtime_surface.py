"""The public control plane must win routing before the CampusCart catch-all."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
            f"<html><body>CampusCart sentinel: {request.url.path}</body></html>"
        )

    monkeypatch.setattr(main, "handle", fake_edge_handler)
    monkeypatch.setattr(
        demo_api,
        "reset_demo",
        lambda: {"ok": True, "run_id": "RUN-routing-test", "checks": []},
    )
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
    assert "CampusCart sentinel" not in response.text


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

    # Unknown v1 API paths are API 404s, not upstream CampusCart pages.
    _assert_json(client.get("/api/v1/not-a-control-route"), expected_status=404)
    assert proxied_paths == []


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
    _assert_json(client.post("/api/v1/demo/run", json={}))
    _assert_json(client.post("/api/v1/demo/restore-golden"))
    _assert_json(client.get("/api/v1/api/v1/demo/status"), expected_status=404)

    assert proxied_paths == []


def test_challenge_assets_and_favicon_keep_their_existing_route_surface(runtime_client):
    client, proxied_paths, _ = runtime_client
    from sb.edge.pipeline import is_exempt

    for path in ("/_sb/challenge.js", "/_sb/static/challenge.js"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/javascript")
        assert "SB_CHALLENGE_ID" in response.text

    # Favicon stays on the existing edge path; pipeline-level exemption is
    # unchanged, and the generic catch-all still hands it to that pipeline.
    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert proxied_paths == ["/favicon.ico"]
    for path in ("/health", "/favicon.ico", "/api/v1/health", "/_sb/challenge.js"):
        assert is_exempt(SimpleNamespace(path=path))


def test_unmatched_site_paths_reach_edge_and_control_routes_precede_catch_all(
    runtime_client,
):
    client, proxied_paths, app = runtime_client

    response = client.get("/catalog/item/42")
    assert response.status_code == 200
    assert "CampusCart sentinel" in response.text
    assert proxied_paths == ["/catalog/item/42"]

    # Keep this assertion compatible with FastAPI versions that represent
    # included routers as internal wrapper objects without a ``path`` field.
    paths = [getattr(route, "path", None) for route in app.routes]
    catch_all_index = next(
        index for index, route in enumerate(app.routes)
        if getattr(route, "name", None) == "catch_all"
    )
    api_fallback_index = paths.index("/api/v1/{path:path}")
    sb_namespace_index = paths.index("/_sb/{path:path}")
    assert api_fallback_index < sb_namespace_index < catch_all_index

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
