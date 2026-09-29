from sb.edge.session import Session
from sb.store.db import reset_db
from sb.store.sessions import get_session, list_sessions, save_session


def test_session_upsert_preserves_first_seen_and_round_trips_telemetry():
    reset_db()
    first = Session(
        session_id="ck-test",
        client_key="client-test",
        ip="192.0.2.10",
        user_agent="Browser/1",
        header_fp="fp-one",
        first_seen="2026-09-30T10:00:00+00:00",
        last_seen="2026-09-30T10:00:00+00:00",
        request_count=1,
        l1_score=10,
        l1_reasons=["L1_HEADER_FP_ANOMALY"],
        l2_score=45,
        l2_signals=["L2_SOFTWARE_GL"],
        layer_path=[{"layer": "L1", "decision": "ALLOW"}],
        pages=["/home"],
        traps_triggered=["TRAP-ROBOTS-01"],
        canaries_exposed=["SB-CAN-0001"],
    )
    save_session(first)

    updated = Session(
        session_id="ck-test",
        client_key="client-test",
        ip="192.0.2.11",
        user_agent="Browser/2",
        header_fp="fp-two",
        first_seen="2026-09-30T11:00:00+00:00",
        last_seen="2026-09-30T11:00:00+00:00",
        request_count=2,
        state="TRAPPED",
        classification="SOPHISTICATED_SCRAPER",
        l1_score=20,
        l1_reasons=["L1_HEADER_FP_ANOMALY", "L1_UNVERIFIED_SESSION"],
        l2_score=45,
        l2_signals=["L2_SOFTWARE_GL"],
        layer_path=[
            {"layer": "L1", "decision": "ALLOW"},
            {"layer": "L3", "decision": "TRAP"},
        ],
        pages=["/home", "/internal/"],
        traps_triggered=["TRAP-ROBOTS-01"],
        canaries_exposed=["SB-CAN-0001", "SB-CAN-0002"],
    )
    save_session(updated)

    loaded = get_session("ck-test")
    assert loaded is not None
    assert loaded.first_seen == first.first_seen
    assert loaded.last_seen == updated.last_seen
    assert loaded.request_count == 2
    assert loaded.ip == updated.ip
    assert loaded.user_agent == updated.user_agent
    assert loaded.header_fp == updated.header_fp
    assert loaded.l1_reasons == updated.l1_reasons
    assert loaded.l2_signals == updated.l2_signals
    assert loaded.layer_path == updated.layer_path
    assert loaded.pages == updated.pages
    assert loaded.traps_triggered == updated.traps_triggered
    assert loaded.canaries_exposed == updated.canaries_exposed
    assert len(list_sessions()) == 1
