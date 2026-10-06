import json
from contextlib import closing

import httpx
import pytest
from sb.canary.seed import seed_canaries
from sb.contracts import SessionDetail, TrafficEvent
from sb.edge.session import sessions
from sb.main import app
from sb.store.db import get_connection, reset_db
from sb.store.sessions import get_session

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "user-agent": UA,
    "accept": "text/html,application/xhtml+xml",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate",
}


def _rows(sql, params=()):
    with closing(get_connection()) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


@pytest.mark.asyncio
async def test_requests_persist_session_and_events(origin_server):
    reset_db()
    sessions.reset()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/persisted-home", headers=HEADERS)
        second = await client.get("/persisted-home", headers=HEADERS)
        assert first.status_code == second.status_code == 200

        summaries = (await client.get("/api/v1/sessions")).json()["sessions"]
        assert len(summaries) >= 1
        session_id = summaries[0]["session_id"]
        response = await client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        api_session = SessionDetail(**response.json())
        api_traffic = (await client.get("/api/v1/traffic/events?after=0&limit=500")).json()["events"]

    db_session = get_session(session_id)
    assert db_session is not None
    assert api_session.session_id == db_session.session_id
    assert db_session.request_count >= 1
    assert db_session.first_seen and db_session.last_seen
    assert "/persisted-home" in db_session.pages

    traffic = _rows(
        "SELECT * FROM traffic_events WHERE session_id = ? ORDER BY seq", (session_id,)
    )
    assert len(traffic) >= 1
    assert [event["event_id"] for event in api_traffic] == [event["event_id"] for event in traffic]
    for row in traffic:
        if isinstance(row.get("reasons"), str):
            row["reasons"] = json.loads(row["reasons"] or "[]")
        TrafficEvent(**row)


@pytest.mark.asyncio
async def test_traffic_overview_aggregates_from_persisted_rows(origin_server):
    reset_db()
    sessions.reset()
    seed_canaries()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/overview-test", headers=HEADERS)
        assert resp.status_code == 200

        overview = (await client.get("/api/v1/overview")).json()

    assert "counts" in overview
    assert "canaries" in overview
    assert "cases" in overview


def test_traffic_logger_rejects_literals_outside_api_contract():
    from sb.edge.pipeline import log_event

    with pytest.raises(ValueError, match="Unsupported traffic layer"):
        log_event(None, None, "L4", "ALLOW", 200)
    with pytest.raises(ValueError, match="Unsupported traffic decision"):
        log_event(None, None, "ORIGIN", "INVALID_DECISION", 200)
