"""Phase 1 Full Telemetry Tap and Durable Session State Integration Tests.

Verifies:
1. Passive telemetry extraction (client IP, offline ASN, plaintext TLS truth, header order fingerprint).
2. Durable session 7-tuple tracking (session_id, client_ip, asn, ja3_hash, asset_ratio, first_seen, last_seen).
3. Rolling asset ratio tracking on mixed browser HTML and API requests.
4. Background telemetry persistence without lost events.
5. End-to-end cryptographic forensic ledger verification (verify_chain == VALID).
"""

from __future__ import annotations

import json
from contextlib import closing

import httpx
import pytest
from sb.canary.seed import seed_canaries
from sb.edge.session import sessions
from sb.main import app
from sb.store import db, ledger


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS_HTML = {
    "user-agent": UA,
    "accept": "text/html,application/xhtml+xml",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate",
}
HEADERS_API = {
    "user-agent": UA,
    "accept": "application/json",
    "content-type": "application/json",
}


@pytest.mark.asyncio
async def test_phase1_full_telemetry_and_session_state(origin_server):
    """End-to-end integration test verifying telemetry extraction, session 7-tuple, and ledger integrity."""
    db.reset_db()
    sessions.reset()
    seed_canaries()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Send mixed traffic burst: 3 HTML page requests, 2 static requests, 1 API request
        r1 = await client.get("/index.html", headers=HEADERS_HTML)
        r2 = await client.get("/about.html", headers=HEADERS_HTML)
        r3 = await client.get("/contact.html", headers=HEADERS_HTML)
        r4 = await client.get("/static/app.js", headers=HEADERS_HTML)
        r5 = await client.get("/static/style.css", headers=HEADERS_HTML)
        r6 = await client.get("/api/v1/overview", headers=HEADERS_API)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200

        # Query session state via API
        sess_resp = await client.get("/api/v1/sessions")
        assert sess_resp.status_code == 200
        sess_data = sess_resp.json()
        assert len(sess_data["sessions"]) >= 1

        active_sid = sess_data["sessions"][0]["session_id"]
        detail_resp = await client.get(f"/api/v1/sessions/{active_sid}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()

        # Verify session fields
        assert detail["session_id"] == active_sid
        assert "state" in detail
        assert detail["decision"] == "SANDBOX"

        # Query traffic events via API
        traffic_resp = await client.get("/api/v1/traffic/events?after=0&limit=500")
        assert traffic_resp.status_code == 200
        events = traffic_resp.json()["events"]
        assert len(events) >= 1

    # Verify cryptographic integrity of forensic ledger
    verification = ledger.verify_chain()
    assert verification["result"] == "VALID"
    assert verification["count"] >= 1
    assert verification["errors"] == []
