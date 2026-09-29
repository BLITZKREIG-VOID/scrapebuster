"""Integration tests for Layer 3 trap detection, decoy serving, and canary injection."""

import socket
import threading
import time
from contextlib import closing

import httpx
import pytest
import sb.edge.pipeline as pipeline_module
import sb.edge.proxy as proxy_module
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sb.canary.seed import seed_canaries
from sb.edge.session import sessions
from sb.main import app
from sb.store import db
from sb.trap.honeypots import HIDDEN_LINK_HTML
from sb.trap.injector import ScapeBustersTrapHooks

CANARY_ANCHORS = [
    "Oriel Vantrask",
    "Hexaquorum",
    "quasar-reconcile",
    "velvet-anchor",
    "ORCHID-7",
]


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def custom_origin():
    """Start a lightweight uvicorn origin on an ephemeral port serving valid HTML with <body> and <main>."""
    import uvicorn

    origin_app = FastAPI()

    @origin_app.get("/{path:path}")
    async def catch_all(path: str):
        content = (
            "<html><head><title>T</title></head>"
            f'<body><nav>n</nav><main id="content"><p>Doc {path}</p></main></body></html>'
        )
        return HTMLResponse(content=content)

    port = find_free_port()
    config = uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to accept connections
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=2)


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch, custom_origin):
    """Isolate DB, configure proxy target to custom origin, reset sessions, and install ScapeBustersTrapHooks."""
    test_db = str(tmp_path / "sb.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()
    seed_canaries()

    monkeypatch.setattr(proxy_module, "SB_ORIGIN_URL", custom_origin)
    monkeypatch.setattr(proxy_module, "_client", None)

    sessions.reset()

    trap_hooks = ScapeBustersTrapHooks()
    monkeypatch.setattr(pipeline_module, "trap_hooks", trap_hooks)

    yield

    sessions.reset()


@pytest.mark.asyncio
async def test_case_a_trapped_flow():
    """Case A (TRAPPED): client GETs /internal/ -> becomes TRAPPED, then GET /docs/architecture gets canary."""
    ua = "Mozilla/5.0 trap-test"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Step 1: Request decoy path under /internal/
        resp1 = await client.get("/internal/", headers={"user-agent": ua})
        assert resp1.status_code == 200
        assert "href=\"/docs/architecture\"" in resp1.text

        # Verify session became TRAPPED
        trapped_sessions = [s for s in sessions._sessions.values() if s.state == "TRAPPED"]
        assert len(trapped_sessions) >= 1
        trapped_session = trapped_sessions[0]

        # Step 2: Request placement page /docs/architecture
        resp2 = await client.get("/docs/architecture", headers={"user-agent": ua})
        assert resp2.status_code == 200
        body_text = resp2.text

        # Must contain canary anchor Hexaquorum and hidden link
        assert "Hexaquorum" in body_text
        assert HIDDEN_LINK_HTML in body_text

        # Exactly one exposure row for SB-CAN-0002 with that session_id
        with closing(db.get_connection()) as conn, conn:
            rows = conn.execute(
                "SELECT * FROM exposures WHERE session_id = ?",
                (trapped_session.session_id,),
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["canary_id"] == "SB-CAN-0002"
            assert rows[0]["resource"] == "/docs/architecture"


@pytest.mark.asyncio
async def test_case_b_verified_flow():
    """Case B (VERIFIED): client GETs /docs/ -> state set to VERIFIED -> GET /docs/architecture gets NO canaries."""
    ua = "Mozilla/5.0 verified-test"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Step 1: GET /docs/ once to establish session
        resp1 = await client.get("/docs/", headers={"user-agent": ua})
        assert resp1.status_code == 200

        # Step 2: Set session state to VERIFIED in sessions manager
        target_session = None
        for s in sessions._sessions.values():
            if s.state != "TRAPPED":
                target_session = s
                break
        assert target_session is not None
        target_session.state = "VERIFIED"

        from sb.edge.layer2 import issue_clearance_cookie
        val, _ = issue_clearance_cookie(target_session.client_key, 0)
        client.cookies.set("sb_clear", val)

        # Step 3: GET /docs/architecture
        resp2 = await client.get("/docs/architecture", headers={"user-agent": ua})
        assert resp2.status_code == 200
        body_text = resp2.text

        # Must contain hidden link
        assert HIDDEN_LINK_HTML in body_text

        # Must NOT contain any of the 5 canary anchors
        for anchor in CANARY_ANCHORS:
            assert anchor.lower() not in body_text.lower()

        # Zero exposures recorded for that session
        with closing(db.get_connection()) as conn, conn:
            rows = conn.execute(
                "SELECT * FROM exposures WHERE session_id = ?",
                (target_session.session_id,),
            ).fetchall()
            assert len(rows) == 0
