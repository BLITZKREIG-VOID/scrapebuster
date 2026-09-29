import httpx
import pytest
from sb.main import app
from sb.store.db import get_connection, reset_db

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


@pytest.mark.asyncio
async def test_proxy_flow(origin_server):
    reset_db()

    import hashlib

    from sb.edge.layer2 import issue_clearance_cookie

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        
        # Pre-issue a clearance cookie so it reaches the proxy directly.
        # Otherwise, as a new session requesting a document, it gets L1_UNVERIFIED_SESSION
        # and reaches the L2 interstitial (which we don't want in this test).
        ck = hashlib.sha256(b"127.0.0.1|" + BROWSER_UA.encode()).hexdigest()[:16]
        val, _ = issue_clearance_cookie(ck, 0)
        client.cookies.set("sb_clear", val)
        
        response = await client.get("/docs/", headers=BROWSER_HEADERS)

        assert response.status_code == 200
        assert b"Origin" in response.content

        # Verify traffic_events logged by pipeline
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM traffic_events ORDER BY seq DESC LIMIT 1")
            event = cursor.fetchone()

            assert event is not None
            assert event["path"] == "/docs/"
            assert event["method"] == "GET"
            assert event["status_code"] == 200
            assert event["layer"] == "L1"
            assert event["decision"] in ("ALLOW", "ESCALATE")
        finally:
            conn.close()
