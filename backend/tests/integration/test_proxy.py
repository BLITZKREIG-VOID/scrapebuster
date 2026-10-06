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

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/docs/", headers=BROWSER_HEADERS)

        assert response.status_code == 200
        assert b"Origin" in response.content

        # Verify traffic_events logged by pipeline
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM traffic_events ORDER BY seq ASC")
            events = cursor.fetchall()

            assert len(events) >= 1
            assert all(event["path"] == "/docs/" for event in events)
            assert all(event["method"] == "GET" for event in events)
            assert all(event["status_code"] == 200 for event in events)
        finally:
            conn.close()


@pytest.mark.asyncio
async def test_robots_txt_is_served_by_the_edge_not_the_origin():
    """No origin fixture: /robots.txt must be served by the edge."""
    reset_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/robots.txt", headers=BROWSER_HEADERS)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "User-agent:" in response.text
