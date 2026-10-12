"""Integration tests for Phase 2 Adaptive AR Classifier and Dynamic Router.

Verifies:
1. End-to-end browser cascade: matures baseline, achieves FAST_PATH, and validates
   byte-identical origin responses (zero mutation).
2. End-to-end scraper reconnaissance: consecutive API calls trigger sticky SANDBOX lock.
3. Proxy restart durability: route baselines and session trust state survive in-memory resets.
4. Classifier status endpoint (/api/v1/classifier/status) and session detail contracts.
5. Hash-chained forensic ledger verification (verify_chain == VALID).
"""

from __future__ import annotations

import httpx
import pytest
from sb.canary.seed import seed_canaries
from sb.classifier.classifier import classifier
from sb.edge.session import sessions
from sb.main import app
from sb.router.router import router
from sb.store import db, ledger


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SCRAPER_UA = "Python-requests/2.31.0 ScraperBot/1.0"

HEADERS_HTML = {
    "user-agent": BROWSER_UA,
    "accept": "text/html,application/xhtml+xml",
    "accept-language": "en-US,en;q=0.9",
}
HEADERS_STATIC = {
    "user-agent": BROWSER_UA,
    "accept": "*/*",
}
HEADERS_SCRAPER = {
    "user-agent": SCRAPER_UA,
    "accept": "application/json",
}


@pytest.fixture(autouse=True)
def reset_state():
    from sb.edge.telemetry import TelemetryTap

    db.reset_db()
    sessions.reset()
    classifier.reset()
    router.reset()
    TelemetryTap.reset()
    seed_canaries()
    yield
    db.reset_db()
    sessions.reset()
    classifier.reset()
    router.reset()
    TelemetryTap.reset()


@pytest.mark.asyncio
async def test_genuine_browser_cascade_fast_path_and_byte_identity(origin_server):
    """Matures route baseline, achieves FAST_PATH, and confirms byte-identical response."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Phase A: Send 12 browser cascades to mature baseline for /catalog
        # Each cascade: 1 HTML page + 3 static assets -> session AR = 3.0
        for i in range(12):
            r_doc = await client.get("/catalog", headers=HEADERS_HTML)
            assert r_doc.status_code == 200
            await client.get(f"/static/bundle_{i}.js", headers=HEADERS_STATIC)
            await client.get(f"/static/theme_{i}.css", headers=HEADERS_STATIC)
            await client.get(f"/static/banner_{i}.png", headers=HEADERS_STATIC)

        # Baseline for /catalog must now be mature
        baseline = classifier.get_baseline("/catalog")
        assert baseline["is_mature"] is True
        assert baseline["sample_count"] >= 10
        assert baseline["ar_ema"] > 0.0

        # Phase B: Subsequent request to /catalog by the same trusted browser session
        fast_resp = await client.get("/catalog", headers=HEADERS_HTML)
        assert fast_resp.status_code == 200

        # Query session detail via API
        sess_list = (await client.get("/api/v1/sessions")).json()["sessions"]
        assert len(sess_list) >= 1
        sid = sess_list[0]["session_id"]
        sess_detail = (await client.get(f"/api/v1/sessions/{sid}")).json()

        assert sess_detail["decision"] == "FAST_PATH"
        assert sess_detail["state"] == "FAST"
        assert sess_detail["trust_score"] >= 70.0
        assert sess_detail["router_decision"] == "FAST_PATH"

        # Byte-identity check: Origin response content vs Proxy response content
        # origin_server returns: <main id='content'>Origin catalog</main>
        expected_origin_bytes = b"<main id='content'>Origin catalog</main>"
        assert fast_resp.content == expected_origin_bytes, (
            f"Expected byte-identical response from origin, got: {fast_resp.content}"
        )


@pytest.mark.asyncio
async def test_scraper_reconnaissance_triggers_sticky_sandbox_lock(origin_server):
    """Scraper harvesting API with zero static assets triggers sticky sandbox lock at 20 requests."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Send 25 consecutive API calls with zero static assets
        for req_idx in range(25):
            resp = await client.get(f"/api/items/{req_idx}", headers=HEADERS_SCRAPER)
            assert resp.status_code == 200

        # Query session state via API
        sess_list = (await client.get("/api/v1/sessions")).json()["sessions"]
        assert len(sess_list) >= 1
        sid = sess_list[0]["session_id"]
        detail = (await client.get(f"/api/v1/sessions/{sid}")).json()

        assert detail["decision"] == "SANDBOX"
        assert detail["state"] == "SANDBOX"
        assert detail["trust_score"] == 0.0
        assert detail["router_decision"] == "SANDBOX"

        # Check internal session object has locked_sandbox == True
        sess_obj = sessions.get(sid)
        assert sess_obj is not None
        assert sess_obj.locked_sandbox is True
        assert sess_obj.ar_anomaly_streak >= 20

        # Sticky check: even if scraper now requests static assets, it remains locked
        await client.get("/static/fake.js", headers=HEADERS_SCRAPER)
        post_static_resp = await client.get("/api/items/99", headers=HEADERS_SCRAPER)
        assert post_static_resp.status_code == 200

        sess_obj_after = sessions.get(sid)
        assert sess_obj_after.locked_sandbox is True
        assert sess_obj_after.state == "SANDBOX"


@pytest.mark.asyncio
async def test_durability_across_proxy_restart(origin_server):
    """FR-2.5: Baseline and session trust state survive in-memory cache resets (proxy restart)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Generate traffic to establish baseline and session state
        for i in range(12):
            await client.get("/products", headers=HEADERS_HTML)
            await client.get(f"/static/asset_{i}.js", headers=HEADERS_STATIC)

        sess_list = (await client.get("/api/v1/sessions")).json()["sessions"]
        sid = sess_list[0]["session_id"]
        pre_detail = (await client.get(f"/api/v1/sessions/{sid}")).json()
        assert pre_detail["trust_score"] > 0.0

        # 2. Simulate proxy process restart: clear in-memory caches
        sessions.reset()
        classifier._cache.clear()
        router.reset()

        # 3. Baseline is reloaded from durable SQLite store
        reloaded_baseline = classifier.get_baseline("/products")
        assert reloaded_baseline["sample_count"] >= 10
        assert reloaded_baseline["is_mature"] is True
        assert reloaded_baseline["ar_ema"] > 0.0

        # 4. Session trust score and state are reloaded from durable SQLite store
        post_detail = (await client.get(f"/api/v1/sessions/{sid}")).json()
        assert post_detail["session_id"] == sid
        assert post_detail["trust_score"] == pre_detail["trust_score"]


@pytest.mark.asyncio
async def test_classifier_status_endpoint(origin_server):
    """Verifies /api/v1/classifier/status endpoint responds with full performance metrics."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/classifier/status")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "ok"
        assert "mutation_mode" in data
        assert "alpha" in data
        assert "trust_threshold" in data
        assert "baseline_min_samples" in data
        assert "metrics" in data
        assert "routes" in data
        assert "total_evaluations" in data["metrics"]


@pytest.mark.asyncio
async def test_forensic_ledger_integrity_after_mixed_traffic(origin_server):
    """Cryptographic hash chain remains VALID after processing fast-path and sandboxed events."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Send mixture of requests
        await client.get("/page1", headers=HEADERS_HTML)
        await client.get("/api/data", headers=HEADERS_SCRAPER)

    verification = ledger.verify_chain()
    assert verification["result"] == "VALID"
    assert verification["errors"] == []
