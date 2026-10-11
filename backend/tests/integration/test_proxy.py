import httpx
import pytest
from sb.main import app
from sb.store.db import get_connection, reset_db
from sb.edge.telemetry import TelemetryTap

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

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/docs/", headers=BROWSER_HEADERS)

        assert response.status_code == 200
        assert b"Origin" in response.content
        assert b"sb-canary" in response.content

        # Flush telemetry to ensure events are persisted
        await TelemetryTap.flush()

        # Verify traffic_events logged by pipeline
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM traffic_events ORDER BY seq ASC")
            events = cursor.fetchall()

            assert len(events) >= 1
            assert any(event["path"] == "/docs/" for event in events)
            assert any(event["decision"] == "SANDBOX" for event in events)
        finally:
            conn.close()


@pytest.mark.asyncio
async def test_proxy_unregistered_routes_forward_and_mutate(origin_server):
    """Unregistered origin paths (including /api/catalog and unregistered /api/v1) forward and mutate."""
    reset_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. /api/catalog forwards to origin and mutates
        response = await client.get("/api/catalog", headers=BROWSER_HEADERS)
        assert response.status_code == 200
        # Pipeline forwards to origin and mutates eligible HTML/JSON response: assert BOTH
        assert b"Origin" in response.content
        assert b"sb-canary" in response.content

        # 2. Unregistered /api/v1 route forwards to origin and mutates
        resp_v1 = await client.get("/api/v1/unknown_catalog", headers=BROWSER_HEADERS)
        assert resp_v1.status_code == 200
        assert b"Origin" in resp_v1.content
        assert b"sb-canary" in resp_v1.content
