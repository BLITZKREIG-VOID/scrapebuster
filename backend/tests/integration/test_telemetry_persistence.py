import asyncio
import hashlib
import json
import re
from contextlib import closing

import httpx
import pytest
from sb.canary.seed import seed_canaries
from sb.contracts import SessionDetail, TrafficEvent
from sb.edge.layer1 import reset_rate_state
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


def _clearance():
    from sb.edge.layer2 import issue_clearance_cookie

    client_key = hashlib.sha256(f"127.0.0.1|{UA}".encode()).hexdigest()[:16]
    value, _ = issue_clearance_cookie(client_key, 0)
    return value


def _rows(sql, params=()):
    with closing(get_connection()) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _solve_pow(challenge_id: str) -> str:
    from sb.edge.layer2 import L2_POW_ZERO_BITS

    nonce = 0
    threshold = 1 << (16 - L2_POW_ZERO_BITS)
    while True:
        digest = hashlib.sha256(f"{challenge_id}:{nonce}".encode()).hexdigest()
        if int(digest[:4], 16) < threshold:
            return str(nonce)
        nonce += 1


def _signals(**changes):
    return {
        "webdriver": False,
        "headlessChrome": False,
        "navigatorUA": UA,
        "outerWidth": 1280,
        "outerHeight": 800,
        "softwareGL": False,
        "languages": ["en-US"],
        "mousemove": 2,
        "scroll": 1,
        "keydown": 1,
        **changes,
    }


@pytest.mark.asyncio
async def test_requests_persist_session_and_one_l1_plus_origin_event_per_request(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.cookies.set("sb_clear", _clearance())
        first = await client.get("/persisted-home", headers=HEADERS)
        second = await client.get("/persisted-home", headers=HEADERS)
        assert first.status_code == second.status_code == 200

        summaries = (await client.get("/api/v1/sessions")).json()["sessions"]
        assert len(summaries) == 1
        session_id = summaries[0]["session_id"]
        response = await client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200
        api_session = SessionDetail(**response.json())
        api_traffic = (await client.get("/api/v1/traffic/events?after=0&limit=500")).json()["events"]

    db_session = get_session(session_id)
    assert db_session is not None
    assert api_session.model_dump() == {
        "session_id": db_session.session_id,
        "classification": db_session.classification,
        "request_count": db_session.request_count,
        "state": db_session.state,
        "client_key": db_session.client_key,
        "ip": db_session.ip,
        "user_agent": db_session.user_agent,
        "header_fp": db_session.header_fp,
        "first_seen": db_session.first_seen,
        "last_seen": db_session.last_seen,
        "l1_score": db_session.l1_score,
        "l1_reasons": db_session.l1_reasons,
        "l2_score": db_session.l2_score,
        "l2_signals": db_session.l2_signals,
        "layer_path": db_session.layer_path,
        "pages": db_session.pages,
        "traps_triggered": db_session.traps_triggered,
        "canaries_exposed": db_session.canaries_exposed,
    }
    assert db_session.request_count == 2
    assert db_session.first_seen and db_session.last_seen
    assert db_session.pages == ["/persisted-home"]

    traffic = _rows(
        "SELECT * FROM traffic_events WHERE session_id = ? ORDER BY seq", (session_id,)
    )
    assert len(traffic) == 4
    assert [(event["layer"], event["decision"]) for event in traffic] == [
        ("L1", "ALLOW"), ("ORIGIN", "ALLOW"),
        ("L1", "ALLOW"), ("ORIGIN", "ALLOW"),
    ]
    assert [event["event_id"] for event in api_traffic] == [event["event_id"] for event in traffic]
    for row in traffic:
        row["reasons"] = json.loads(row["reasons"] or "[]")
        TrafficEvent(**row)


@pytest.mark.asyncio
async def test_trap_exposure_and_overview_aggregate_from_persisted_rows(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    seed_canaries()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        challenge = await client.get("/telemetry-start", headers=HEADERS)
        match = re.search(r'SB_CHALLENGE_ID = "(ch-[^"]+)"', challenge.text)
        assert challenge.status_code == 200 and match
        challenge_id = match.group(1)
        await asyncio.sleep(1.05)
        verified = await client.post(
            "/_sb/verify",
            headers=HEADERS,
            json={
                "challenge_id": challenge_id,
                "nonce": _solve_pow(challenge_id),
                "signals": _signals(
                    softwareGL=True,
                    languages=[],
                    mousemove=0,
                    scroll=0,
                    keydown=0,
                ),
            },
        )
        assert verified.status_code == 200
        response = await client.get("/internal/", headers=HEADERS)
        assert response.status_code == 200
        assert "Oriel Vantrask" in response.text

        listed = (await client.get("/api/v1/sessions")).json()["sessions"]
        session_id = listed[0]["session_id"]
        session_response = await client.get(f"/api/v1/sessions/{session_id}")
        session_data = SessionDetail(**session_response.json())
        events_response = await client.get("/api/v1/traffic/events?after=0&limit=500")
        events_data = events_response.json()["events"]
        with closing(get_connection()) as conn:
            conn.execute(
                """INSERT INTO cases (
                    case_id, run_id, created_at, status, confidence,
                    primary_canary_id, session_ids, probe_ids, findings,
                    evidence, statement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "CASE-TELEMETRY-1", "RUN-TELEMETRY", "2026-09-30T12:00:00+00:00",
                    "PROVENANCE_SIGNAL_DETECTED", "HIGH", "SB-CAN-0001",
                    json.dumps([session_id]), json.dumps([]), json.dumps([]), json.dumps({}),
                    "telemetry integration case",
                ),
            )
        overview = (await client.get("/api/v1/overview")).json()

    assert session_data.state == "TRAPPED"
    assert "TRAP-ROBOTS-01" in session_data.traps_triggered
    assert len(session_data.canaries_exposed) == 5
    assert session_data.l1_reasons
    assert {"L2_SOFTWARE_GL", "L2_NO_LANGUAGES", "L2_NO_INTERACTION"} <= set(session_data.l2_signals)
    traps = _rows("SELECT * FROM trap_hits WHERE session_id = ?", (session_id,))
    exposures = _rows("SELECT * FROM exposures WHERE session_id = ?", (session_id,))
    assert len(traps) == 1
    assert len(exposures) == 5
    assert {event["session_id"] for event in exposures} == {session_id}
    assert [(event["layer"], event["decision"]) for event in events_data] == [
        ("L1", "ESCALATE"),
        ("L2", "CHALLENGE"),
        ("L2", "TRAP"),
        ("L1", "ESCALATE"),
        ("L3", "TRAP"),
    ]
    assert any(event["layer"] == "L3" and event["decision"] == "TRAP" for event in events_data)
    for event in events_data:
        TrafficEvent(**event)

    db_counts = {row["decision"]: row["count"] for row in _rows(
        "SELECT decision, COUNT(*) AS count FROM traffic_events GROUP BY decision"
    )}
    for decision, count in db_counts.items():
        assert overview["counts"][decision] == count
    with closing(get_connection()) as conn:
        active = conn.execute("SELECT COUNT(*) FROM canaries WHERE status='ACTIVE'").fetchone()[0]
        exposed = conn.execute("SELECT COUNT(*) FROM canaries WHERE status='EXPOSED'").fetchone()[0]
        observed = conn.execute("SELECT COUNT(*) FROM canaries WHERE status='OBSERVED'").fetchone()[0]
        case_total = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        case_detected = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE status='PROVENANCE_SIGNAL_DETECTED'"
        ).fetchone()[0]
    assert overview["canaries"] == {"active": active, "exposed": exposed, "observed": observed}
    assert overview["cases"] == {"total": case_total, "detected": case_detected}


@pytest.mark.asyncio
async def test_l2_pass_and_challenge_events_are_persisted(origin_server):
    reset_db()
    sessions.reset()
    reset_rate_state()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        challenged = await client.get("/telemetry-pass", headers=HEADERS)
        match = re.search(r'SB_CHALLENGE_ID = "(ch-[^"]+)"', challenged.text)
        assert challenged.status_code == 200 and match
        challenge_id = match.group(1)
        await asyncio.sleep(1.05)
        verified = await client.post(
            "/_sb/verify",
            headers=HEADERS,
            json={"challenge_id": challenge_id, "nonce": _solve_pow(challenge_id), "signals": _signals()},
        )
        assert verified.status_code == 200
        summaries = (await client.get("/api/v1/sessions")).json()["sessions"]
        session_id = summaries[0]["session_id"]
        detail = SessionDetail(**(await client.get(f"/api/v1/sessions/{session_id}")).json())
        events = (await client.get("/api/v1/traffic/events?after=0&limit=500")).json()["events"]

    assert detail.request_count == 2
    assert detail.state == "VERIFIED"
    assert [(event["layer"], event["decision"]) for event in events] == [
        ("L1", "ESCALATE"), ("L2", "CHALLENGE"), ("L2", "PASS"),
    ]
    assert sum(event["decision"] == "ESCALATE" for event in events) == 1
    for event in events:
        TrafficEvent(**event)


def test_traffic_logger_rejects_literals_outside_api_contract():
    from sb.edge.pipeline import log_event

    with pytest.raises(ValueError, match="Unsupported traffic layer"):
        log_event(None, None, "L4", "ALLOW", 200)
    with pytest.raises(ValueError, match="Unsupported traffic decision"):
        log_event(None, None, "L1", "ESCALATE_TWICE", 200)
