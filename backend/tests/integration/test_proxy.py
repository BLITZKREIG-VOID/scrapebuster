import httpx
import pytest
from sb.main import app
from sb.store.db import get_connection, reset_db


@pytest.mark.asyncio
async def test_proxy_flow(origin_server):
    reset_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/docs/")

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
            assert event["decision"] in ("ALLOW", "ESCALATE", "CHALLENGE")
        finally:
            conn.close()
