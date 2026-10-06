"""Unit tests for offense path matching and hit persistence."""

from types import SimpleNamespace

from sb.offense.honeypots import get_configured_trap_api_path
from sb.offense.layer3 import classify_request, list_trap_hits, match_trap


def test_match_trap_decoy_api(monkeypatch):
    monkeypatch.setenv("SB_TRAP_API_PATH", "/api/v1/decoy")
    api_path = get_configured_trap_api_path()
    assert api_path == "/api/v1/decoy"

    hit = match_trap("/api/v1/decoy")
    assert hit is not None
    assert hit.trap_id == "TRAP-DECOY-01"
    assert hit.trap_type == "decoy_api"

    hit_slash = match_trap("/api/v1/decoy/")
    assert hit_slash is not None
    assert hit_slash.trap_id == "TRAP-DECOY-01"


def test_match_trap_configured_paths(monkeypatch):
    monkeypatch.setenv("SB_TRAP_PATHS", '["/hidden/trap", "/honeypot"]')

    hit = match_trap("/hidden/trap")
    assert hit is not None
    assert hit.trap_id == "TRAP-PATH-01"
    assert hit.trap_type == "trap_path"

    # Non-trap paths return None
    assert match_trap("/docs/api") is None
    assert match_trap("/") is None


def test_classify_request_hit_and_miss(monkeypatch):
    monkeypatch.setenv("SB_TRAP_PATHS", '["/hidden/trap"]')

    # Hit writes exactly one row
    ctx_hit = SimpleNamespace(path="/hidden/trap")
    sess_hit = SimpleNamespace(session_id="sess-001", state="SANDBOX")
    hit = classify_request(ctx_hit, sess_hit)
    assert hit is not None
    assert hit.trap_id == "TRAP-PATH-01"

    hits = list_trap_hits("sess-001")
    assert len(hits) == 1
    assert hits[0]["trap_id"] == "TRAP-PATH-01"
    assert hits[0]["session_id"] == "sess-001"
    assert hits[0]["path"] == "/hidden/trap"
    assert hits[0]["hit_id"].startswith("HIT-")

    # Miss writes zero rows
    ctx_miss = SimpleNamespace(path="/docs/")
    sess_miss = SimpleNamespace(session_id="sess-002", state="SANDBOX")
    miss = classify_request(ctx_miss, sess_miss)
    assert miss is None

    hits_miss = list_trap_hits("sess-002")
    assert len(hits_miss) == 0
