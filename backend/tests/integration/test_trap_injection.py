"""Integration tests for offense detection, decoy serving, and canary injection."""

import socket
import threading
import time
from contextlib import closing

import httpx
import pytest
import sb.edge.proxy as proxy_module
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sb.canary.seed import seed_canaries
from sb.edge.session import sessions
from sb.main import app
from sb.store import db


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
    """Isolate DB, configure proxy target to custom origin, reset sessions."""
    test_db = str(tmp_path / "sb.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()
    seed_canaries()

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", custom_origin)
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", custom_origin)
    monkeypatch.setattr(proxy_module, "_client", None)

    sessions.reset()

    yield

    sessions.reset()


@pytest.mark.asyncio
async def test_offense_response_transformation():
    """Client request reaches origin and receives transformed response."""
    ua = "Mozilla/5.0 offense-test"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/docs/architecture", headers={"user-agent": ua})
        assert resp.status_code == 200
        assert b"docs/architecture" in resp.content
        assert b"sb-canary" in resp.content
        assert b"SB-CANARY-" in resp.content
