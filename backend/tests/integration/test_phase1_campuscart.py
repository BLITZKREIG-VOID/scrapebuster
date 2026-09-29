"""Phase 1 Acceptance and Integration Tests — CampusCart Baseline.

Focused integration suite covering Phase 1 risk vectors:
1. Inbound hostile Host header and malicious absolute/scheme-relative path cannot select
   arbitrary upstream hosts (verified via ASGI pipeline with captured mock transport).
2. Upstream hop-by-hop headers stripped; identity encoding and response metadata preserved.
3. Edge response transformation: hidden link injection, content-length consistency, and
   content-encoding removal.
4. Canary exposure isolation: untrapped/ordinary requests receive no canaries and record
   no exposures; trapped requests accessing the /internal lure receive active canaries.
"""

from __future__ import annotations

import hashlib
from contextlib import closing
from urllib.parse import urlsplit

import httpx
import pytest

from sb.canary.seed import seed_canaries
from sb.config import SB_ORIGIN_URL
from sb.edge import layer1
from sb.edge.layer2 import issue_clearance_cookie
import sb.edge.proxy as proxy_module
from sb.edge.session import sessions
from sb.main import app
from sb.store import db
from sb.trap.honeypots import HIDDEN_LINK_HTML

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "user-agent": BROWSER_UA,
    "accept": "text/html,application/xhtml+xml",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate",
}
CANARY_ANCHORS = [
    "Oriel Vantrask",
    "Hexaquorum",
    "quasar-reconcile",
    "velvet-anchor",
    "ORCHID-7",
]


def _issue_clearance(client_key: str = "") -> str:
    if not client_key:
        client_key = hashlib.sha256(b"127.0.0.1|" + BROWSER_UA.encode()).hexdigest()[:16]
    val, _ = issue_clearance_cookie(client_key, 0)
    return val


@pytest.fixture(autouse=True)
def cleanup_state():
    """Ensure full test suite safety: reset sessions, rate windows, DB, and client singleton."""
    db.reset_db()
    sessions.reset()
    with layer1._RATE_LOCK:
        layer1._client_timestamps.clear()
    proxy_module._client = None
    yield
    db.reset_db()
    sessions.reset()
    with layer1._RATE_LOCK:
        layer1._client_timestamps.clear()
    proxy_module._client = None


# ---------------------------------------------------------------------------
# 1. Hostile Host & Path Cannot Select Arbitrary Upstream (ASGI pipeline)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hostile_host_and_malicious_path_cannot_select_arbitrary_upstream(monkeypatch):
    """Hostile Host, connection-token hop-by-hop headers, and scheme-relative path are neutralized."""
    captured: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="<html><body>ok</body></html>")

    mock_client = httpx.AsyncClient(
        base_url=SB_ORIGIN_URL,
        transport=httpx.MockTransport(mock_handler),
    )
    monkeypatch.setattr(proxy_module, "_client", mock_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.cookies.set("sb_clear", _issue_clearance())
        headers = {
            **BROWSER_HEADERS,
            "host": "evil-attacker.example.com",
            "connection": "close, x-custom-hop",
            "keep-alive": "timeout=5",
            "x-custom-hop": "secret-token",
        }
        # Inbound request with scheme-relative malicious path attempting SSRF diversion
        resp = await client.get("//evil.com/catalog?page=1", headers=headers)

    assert resp.status_code == 200
    assert len(captured) == 1
    req = captured[0]

    # Destination URL strictly targets configured origin; evil.com is stripped
    assert str(req.url) == f"{SB_ORIGIN_URL.rstrip('/')}/catalog?page=1"
    # Host header rewritten to origin netloc
    assert req.headers["host"] == urlsplit(SB_ORIGIN_URL).netloc
    # Standard and connection-nominated hop-by-hop headers filtered; permit HTTPX keep-alive
    assert req.headers.get("connection") != "close, x-custom-hop"
    assert "close" not in req.headers.get("connection", "")
    assert req.headers.get("connection") in (None, "keep-alive")
    assert "keep-alive" not in req.headers
    assert "x-custom-hop" not in req.headers
    # Identity encoding preserved
    assert req.headers["accept-encoding"] == "identity"


# ---------------------------------------------------------------------------
# 2. Response Transformation & Metadata Consistency
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_response_transform_and_encoding_metadata(monkeypatch):
    """Hidden link is injected; upstream content-encoding is stripped and content-length updated."""
    upstream_html = "<html><head><title>Test</title></head><body><p>Content</p></body></html>"

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html; charset=utf-8",
                "content-encoding": "identity",
                "content-length": str(len(upstream_html)),
            },
            text=upstream_html,
        )

    mock_client = httpx.AsyncClient(
        base_url=SB_ORIGIN_URL,
        transport=httpx.MockTransport(mock_handler),
    )
    monkeypatch.setattr(proxy_module, "_client", mock_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.cookies.set("sb_clear", _issue_clearance())
        resp = await client.get("/", headers=BROWSER_HEADERS)

    assert resp.status_code == 200
    assert HIDDEN_LINK_HTML in resp.text
    # Pipeline removes content-encoding to avoid browser decompression mismatches
    assert "content-encoding" not in resp.headers
    assert int(resp.headers.get("content-length", len(resp.content))) == len(resp.content)


# ---------------------------------------------------------------------------
# 3. TRAP vs Ordinary User Canary Exposure via Actual Edge
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_trap_vs_ordinary_canary_exposure(tmp_path, monkeypatch):
    """Untrapped requests never receive canaries; trapped requests hitting /internal receive all canaries."""
    test_db = str(tmp_path / "sb_canary_test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()
    seed_canaries()
    sessions.reset()

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="<html><body>Origin</body></html>")

    mock_client = httpx.AsyncClient(
        base_url=SB_ORIGIN_URL,
        transport=httpx.MockTransport(mock_handler),
    )
    monkeypatch.setattr(proxy_module, "_client", mock_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # A. Ordinary / untrapped flow: normal document access
        client.cookies.set("sb_clear", _issue_clearance())
        resp_ordinary = await client.get("/", headers=BROWSER_HEADERS)
        assert resp_ordinary.status_code == 200
        assert HIDDEN_LINK_HTML in resp_ordinary.text
        for anchor in CANARY_ANCHORS:
            assert anchor not in resp_ordinary.text

        with closing(db.get_connection()) as conn:
            assert conn.execute("SELECT COUNT(*) FROM exposures").fetchone()[0] == 0

        # B. Trapped flow: touching /internal triggers TRAP-ROBOTS-01 lure
        resp_trapped = await client.get("/internal/", headers=BROWSER_HEADERS)
        assert resp_trapped.status_code == 200
        assert HIDDEN_LINK_HTML in resp_trapped.text
        for anchor in CANARY_ANCHORS:
            assert anchor in resp_trapped.text

        with closing(db.get_connection()) as conn:
            count = conn.execute("SELECT COUNT(*) FROM exposures WHERE resource = '/internal/'").fetchone()[0]
            assert count == len(CANARY_ANCHORS)

