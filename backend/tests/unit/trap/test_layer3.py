"""Unit tests for Layer 3 trap matching and hit persistence."""

from types import SimpleNamespace

from sb.trap.honeypots import DECOY_API_PATH
from sb.trap.layer3 import classify_request, list_trap_hits, match_trap


def test_match_trap_paths():
    # Hidden link paths
    hit1 = match_trap("/docs/archive/legacy-index")
    assert hit1 is not None
    assert hit1.trap_id == "TRAP-LINK-01"
    assert hit1.trap_type == "hidden_link"
    assert hit1.path == "/docs/archive/legacy-index"

    hit1_slash = match_trap("/docs/archive/legacy-index/")
    assert hit1_slash is not None
    assert hit1_slash.trap_id == "TRAP-LINK-01"
    assert hit1_slash.trap_type == "hidden_link"

    # Robots prefix and /internal
    hit2 = match_trap("/internal/")
    assert hit2 is not None
    assert hit2.trap_id == "TRAP-ROBOTS-01"
    assert hit2.trap_type == "robots_disallowed"

    hit3 = match_trap("/internal/anything")
    assert hit3 is not None
    assert hit3.trap_id == "TRAP-ROBOTS-01"
    assert hit3.trap_type == "robots_disallowed"

    hit4 = match_trap("/internal")
    assert hit4 is not None
    assert hit4.trap_id == "TRAP-ROBOTS-01"
    assert hit4.trap_type == "robots_disallowed"

    # Decoy API path takes precedence over robots rule
    hit_decoy = match_trap(DECOY_API_PATH)
    assert hit_decoy is not None
    assert hit_decoy.trap_id == "TRAP-DECOY-01"
    assert hit_decoy.trap_type == "decoy_api"

    hit_decoy_slash = match_trap(DECOY_API_PATH + "/")
    assert hit_decoy_slash is not None
    assert hit_decoy_slash.trap_id == "TRAP-DECOY-01"
    assert hit_decoy_slash.trap_type == "decoy_api"

    # Non-trap paths return None
    assert match_trap("/docs/api") is None
    assert match_trap("/") is None
    assert match_trap("/docs/") is None


def test_match_trap_l2_band():
    # In-band boundaries
    session_40 = SimpleNamespace(state="NEW", l2_score=40)
    hit_40 = match_trap("/docs/", session=session_40)
    assert hit_40 is not None
    assert hit_40.trap_id == "TRAP-BAND-L2"
    assert hit_40.trap_type == "l2_band"

    session_69 = SimpleNamespace(state="NEW", l2_score=69)
    hit_69 = match_trap("/docs/", session=session_69)
    assert hit_69 is not None
    assert hit_69.trap_id == "TRAP-BAND-L2"
    assert hit_69.trap_type == "l2_band"

    # Out of band
    session_39 = SimpleNamespace(state="NEW", l2_score=39)
    assert match_trap("/docs/", session=session_39) is None

    session_70 = SimpleNamespace(state="NEW", l2_score=70)
    assert match_trap("/docs/", session=session_70) is None

    # TRAPPED session in band should return None (already trapped)
    session_trapped = SimpleNamespace(state="TRAPPED", l2_score=50)
    assert match_trap("/docs/", session=session_trapped) is None


def test_classify_request_hit_and_miss():
    # Hit writes exactly one row
    ctx_hit = SimpleNamespace(path="/internal/")
    sess_hit = SimpleNamespace(session_id="sess-001", state="NEW")
    hit = classify_request(ctx_hit, sess_hit)
    assert hit is not None
    assert hit.trap_id == "TRAP-ROBOTS-01"
    assert hit.trap_type == "robots_disallowed"

    hits = list_trap_hits("sess-001")
    assert len(hits) == 1
    assert hits[0]["trap_id"] == "TRAP-ROBOTS-01"
    assert hits[0]["trap_type"] == "robots_disallowed"
    assert hits[0]["session_id"] == "sess-001"
    assert hits[0]["path"] == "/internal/"
    assert hits[0]["hit_id"].startswith("HIT-")
    assert hits[0]["ts"]

    # Miss writes zero rows
    ctx_miss = SimpleNamespace(path="/docs/")
    sess_miss = SimpleNamespace(session_id="sess-002", state="NEW", l2_score=0)
    miss = classify_request(ctx_miss, sess_miss)
    assert miss is None

    hits_miss = list_trap_hits("sess-002")
    assert len(hits_miss) == 0

    # Total rows in trap_hits table is exactly 1
    all_hits = list_trap_hits()
    assert len(all_hits) == 1
