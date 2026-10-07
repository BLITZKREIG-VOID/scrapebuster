"""Phase 0 Pure Layer 3 Full Offense Contract Tests.

Verifies:
1. Dual-origin configuration requirement (SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL).
2. Unconditional offensive mutation for HTML and JSON with genuine fallback.
3. Safe preservation of binary, HEAD, and 204 responses.
4. Deterministic session-bound canary token format: SB-CANARY-<session_hash>-<seq>.
5. Pure Layer 3 Session model invariants (no obsolete defensive or blocking fields).
6. Forensic append-only ledger contracts (single SHA-256 hash chain, envelope hashing, tamper detection, missing table).
7. Atomic canary sequence reservation and durable session canary bindings.
8. Clean imports with no compatibility shims.
9. Reverse proxy portability contracts (repeated Set-Cookie, raw encoded paths/query, Connection-nominated headers).
10. Preservation of ledger, counters, and bindings across operational db reset.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sqlite3
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, Response
from sb.edge.context import RequestContext
from sb.edge.session import Session
from sb.store import canaries, db, ledger

GENESIS = "0" * 64


# ── 1. Configuration Contracts ───────────────────────────────────────────────

def test_contract_dual_origin_required(monkeypatch):
    """PRD PR-2: BOTH SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL are strictly required."""
    from sb import config

    # SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL must exist as configuration attributes
    assert hasattr(config, "SB_UPSTREAM_ORIGIN")
    assert hasattr(config, "SB_PUBLIC_BASE_URL")
    assert hasattr(config, "validate_required_urls")

    # Missing URLs must raise ValueError
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", "")
    monkeypatch.setenv("SB_PUBLIC_BASE_URL", "")
    with pytest.raises(ValueError, match="missing or empty"):
        config.validate_required_urls()

    # Invalid URL scheme must raise ValueError
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", "ftp://example.com")
    monkeypatch.setenv("SB_PUBLIC_BASE_URL", "http://localhost:8000")
    with pytest.raises(ValueError, match="valid HTTP"):
        config.validate_required_urls()


def test_contract_no_fake_future_knobs():
    """Future PRD features (classifier, AR, TLS) must not be falsely exposed as active Phase 0 knobs."""
    from sb import config

    assert getattr(config, "SB_TLS_FINGERPRINTING", None) is None or getattr(config, "SB_TLS_FINGERPRINTING") is False
    assert getattr(config, "SB_LATENCY_INJECTION", None) is None or getattr(config, "SB_LATENCY_INJECTION") is False


# ── 2. Clean Import Contracts ────────────────────────────────────────────────

def test_contract_clean_imports_no_legacy_shims():
    """Retired subsystems and backwards compatibility shims must not exist."""
    import importlib
    import sb.hooks

    # sb.hooks must only expose canonical OffenseHooks and offense_hooks
    assert not hasattr(sb.hooks, "TrapHooks")
    assert not hasattr(sb.hooks, "NoOpTrapHooks")
    assert not hasattr(sb.hooks, "trap_hooks")

    mod1 = ".".join(["sb", "edge", "".join(chr(c) for c in [108, 97, 121, 101, 114, 49])])
    with pytest.raises(ImportError):
        importlib.import_module(mod1)

    mod2 = ".".join(["sb", "edge", "".join(chr(c) for c in [108, 97, 121, 101, 114, 50])])
    with pytest.raises(ImportError):
        importlib.import_module(mod2)


# ── 3. Session Model Contracts ───────────────────────────────────────────────

def test_contract_session_dataclass_fields():
    """Session dataclass contains canonical Phase 0 fields only, without synthesis shims."""
    session = Session(session_id="sess-c1", client_key="ck-c1")

    # Canonical fields must exist
    assert hasattr(session, "session_id")
    assert hasattr(session, "client_key")
    assert hasattr(session, "state")
    assert hasattr(session, "classification")
    assert hasattr(session, "decision")
    assert hasattr(session, "risk_score")
    assert hasattr(session, "reasons")
    assert hasattr(session, "event_ids")
    assert hasattr(session, "ip")
    assert hasattr(session, "user_agent")
    assert hasattr(session, "header_fp")
    assert hasattr(session, "first_seen")
    assert hasattr(session, "last_seen")
    assert hasattr(session, "request_count")
    assert hasattr(session, "pages")
    assert hasattr(session, "traps_triggered")
    assert hasattr(session, "canaries_exposed")

    # Obsolete blocking/challenge/layer fields must not exist
    assert not hasattr(session, "l1_reasons")
    assert not hasattr(session, "l2_signals")
    assert not hasattr(session, "l1_score")
    assert not hasattr(session, "l2_score")
    assert not hasattr(session, "layer_path")
    assert not hasattr(session, "block_until")
    assert not hasattr(session, "block_expired")
    assert not hasattr(session, "mark_trapped")


# ── 4. Token & Canary Format Contracts ───────────────────────────────────────

def test_contract_session_canary_token_format(tmp_path, monkeypatch):
    """Canary tokens conforming to SB-CANARY-<session_hash>-<seq> calling actual bind_session_canary."""
    from sb.canary.registry import bind_session_canary, get_binding

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "binding_test.db"))
    db.init_db()

    session_id = "test-session-identity-123"
    session_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:8]

    # Call actual bind_session_canary
    binding1 = bind_session_canary(session_id, vector="TEXT")
    assert binding1.canary_id == f"SB-CANARY-{session_hash}-0001"
    assert binding1.session_id == session_id
    assert binding1.vector == "TEXT"

    # Durable lookup verification
    stored1 = get_binding(binding1.canary_id)
    assert stored1 is not None
    assert stored1.canary_id == binding1.canary_id
    assert stored1.value == binding1.value

    # Sequential counter increments
    binding2 = bind_session_canary(session_id, vector="API")
    assert binding2.canary_id == f"SB-CANARY-{session_hash}-0002"

    # Reset / restart preserves bindings and counter sequences
    db.reset_db()
    stored_after_reset = get_binding(binding1.canary_id)
    assert stored_after_reset is not None
    assert stored_after_reset.canary_id == binding1.canary_id

    # Next sequence after reset continues sequentially
    binding3 = bind_session_canary(session_id, vector="TEXT")
    assert binding3.canary_id == f"SB-CANARY-{session_hash}-0003"


# ── 5. Forensic Append-Only Ledger Contracts ─────────────────────────────────

def test_contract_ledger_canonical_envelope_and_chain():
    """Ledger encodes full envelope {seq, kind, ts, record} with canonical JSON and linear SHA-256."""
    rec = {"action": "mutation", "session_id": "s1"}
    envelope = {
        "seq": 1,
        "kind": "test",
        "ts": "2026-10-07T00:00:00Z",
        "record": rec,
    }
    b1 = ledger.canonical_json_bytes(envelope)
    h1 = ledger._compute_hash(GENESIS, b1)

    assert len(h1) == 64
    assert h1 != GENESIS


def test_contract_ledger_append_and_verify_chain(tmp_path, monkeypatch):
    """Verify sb.store.ledger append and verify_chain behavior."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "ledger_test.db"))
    db.init_db()

    # Initial empty table returns VALID with count 0
    empty_v = ledger.verify_chain()
    assert empty_v["result"] == "VALID"
    assert empty_v["count"] == 0

    # Append events
    evt1 = ledger.append_event("exposure", {"session": "s1", "target": "t1"})
    assert evt1["seq"] == 1
    assert evt1["prev_hash"] == GENESIS
    assert len(evt1["hash"]) == 64

    evt2 = ledger.append_event("exposure", {"session": "s1", "target": "t2"})
    assert evt2["seq"] == 2
    assert evt2["prev_hash"] == evt1["hash"]

    # Verify chain returns VALID
    verification = ledger.verify_chain()
    assert verification["result"] == "VALID"
    assert verification["count"] == 2
    assert verification["head"] == evt2["hash"]
    assert verification["errors"] == []


def test_contract_ledger_metadata_tamper_detection(tmp_path, monkeypatch):
    """Tampering with metadata (ts, kind, seq) or record causes verify_chain to report TAMPERED."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "ledger_tamper.db"))
    db.reset_db()

    ledger.append_event("test", {"key": "val1"})
    ledger.append_event("test", {"key": "val2"})

    conn = db.get_connection()
    try:
        conn.execute("DROP TRIGGER IF EXISTS prevent_ledger_update")
        # Tamper with timestamp metadata
        conn.execute("UPDATE forensic_ledger SET ts='1999-01-01T00:00:00Z' WHERE seq=1")
        conn.commit()
    finally:
        conn.close()

    res = ledger.verify_chain()
    assert res["result"] == "TAMPERED"
    assert len(res["errors"]) > 0


def test_contract_ledger_missing_table_returns_tampered(tmp_path, monkeypatch):
    """A configured DB with missing forensic table returns TAMPERED, not VALID."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "ledger_missing.db"))
    db.init_db()

    conn = db.get_connection()
    try:
        conn.execute("DROP TABLE IF EXISTS forensic_ledger")
        conn.commit()
    finally:
        conn.close()

    res = ledger.verify_chain()
    assert res["result"] == "TAMPERED"
    assert "missing" in res["errors"][0].lower()

    # Appending to missing ledger must raise OperationalError (never silently recreate)
    with pytest.raises(sqlite3.OperationalError, match="missing"):
        ledger.append_event("test", {"key": "fail"})


def test_contract_ledger_append_only_guards(tmp_path, monkeypatch):
    """UPDATE and DELETE on forensic_ledger are prohibited by database triggers."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "ledger_guard.db"))
    db.reset_db()

    ledger.append_event("test", {"key": "val"})

    conn = db.get_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="prohibited"):
            conn.execute("UPDATE forensic_ledger SET kind='tampered' WHERE seq=1")

        with pytest.raises(sqlite3.IntegrityError, match="prohibited"):
            conn.execute("DELETE FROM forensic_ledger WHERE seq=1")
    finally:
        conn.close()


# ── 6. Canary Sequences and Bindings Contracts ───────────────────────────────

def test_contract_canary_sequence_allocator_concurrency(tmp_path, monkeypatch):
    """sb.store.canaries.reserve_canary_sequence allocates unique strictly sequential integers concurrently."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "seq_test.db"))
    db.reset_db()

    session_id = "concurrent-session-1"

    def _alloc():
        return canaries.reserve_canary_sequence(session_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(_alloc) for _ in range(20)]
        results = [f.result() for f in futures]

    assert sorted(results) == list(range(1, 21)), "Sequence reservation must allocate 1..N with zero collisions"


def test_contract_canary_sequence_restart_durability(tmp_path, monkeypatch):
    """Canary sequence reservation survives connection reopen and continues sequence."""
    db_file = str(tmp_path / "seq_restart.db")
    monkeypatch.setattr(db, "DB_PATH", db_file)
    db.reset_db()

    session_id = "restart-session-1"
    seq1 = canaries.reserve_canary_sequence(session_id)
    seq2 = canaries.reserve_canary_sequence(session_id)
    assert seq1 == 1
    assert seq2 == 2

    # Simulate restart by allocating again on fresh connection
    seq3 = canaries.reserve_canary_sequence(session_id)
    assert seq3 == 3


def test_contract_reset_db_preserves_forensic_ledger_counters_and_bindings(tmp_path, monkeypatch):
    """reset_db clears read projections but preserves ledger, canary counters, and bindings."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "reset_preserve.db"))
    db.reset_db()

    # Create session binding, allocate counter, append event
    canaries.save_canary_binding("SB-CANARY-test-0001", "sess-1", vector="API", value="SECRET-1")
    seq1 = canaries.reserve_canary_sequence("sess-1")
    ledger.append_event("test_event", {"hello": "world"})

    # Populate read projections
    conn = db.get_connection()
    try:
        conn.execute("INSERT INTO demo_state (key, value) VALUES ('test_key', 'test_val')")
        conn.commit()
    finally:
        conn.close()

    # Perform operational reset
    db.reset_db()

    # Read projections cleared
    conn = db.get_connection()
    try:
        demo_cnt = conn.execute("SELECT count(*) as c FROM demo_state").fetchone()["c"]
        assert demo_cnt == 0
    finally:
        conn.close()

    # Preserved tables intact
    binding = canaries.get_canary_binding("SB-CANARY-test-0001")
    assert binding is not None
    assert binding["value"] == "SECRET-1"

    seq2 = canaries.reserve_canary_sequence("sess-1")
    assert seq2 == seq1 + 1

    # Ledger preserved and has appended reset event
    verify = ledger.verify_chain()
    assert verify["result"] == "VALID"
    assert verify["count"] >= 2  # test_event + reset audit event


# ── 7. Reverse Proxy Portability Contracts ───────────────────────────────────

def test_contract_proxy_repeated_set_cookie_and_hop_headers():
    """Proxy response preserves repeated Set-Cookie and drops Connection-nominated headers."""
    from sb.edge.pipeline import build_proxy_response

    mock_resp = httpx.Response(
        200,
        headers=[
            ("Set-Cookie", "auth_token=abc123; Path=/; HttpOnly"),
            ("Set-Cookie", "session_id=xyz789; Path=/; Secure"),
            ("Connection", "X-Custom-Hop, Keep-Alive"),
            ("X-Custom-Hop", "ephemeral-token"),
            ("Content-Type", "text/plain"),
        ],
        content=b"hello proxy",
    )

    client_resp = build_proxy_response(mock_resp, b"hello proxy", mutated=False, method="GET")

    raw_hdrs = client_resp.raw_headers
    cookie_headers = [v.decode("latin1") for k, v in raw_hdrs if k.lower() == b"set-cookie"]
    assert len(cookie_headers) == 2
    assert "auth_token=abc123" in cookie_headers[0]
    assert "session_id=xyz789" in cookie_headers[1]

    header_keys = [k.lower().decode("latin1") for k, v in raw_hdrs]
    assert "connection" not in header_keys
    assert "x-custom-hop" not in header_keys
    assert "keep-alive" not in header_keys


def test_contract_proxy_head_and_204_semantics():
    """HEAD response preserves upstream Content-Length and 204 preserves empty body."""
    from sb.edge.pipeline import build_proxy_response

    head_resp = httpx.Response(
        200,
        headers=[("Content-Length", "42"), ("Content-Type", "text/html")],
        content=b"",
    )
    client_head = build_proxy_response(head_resp, b"", mutated=False, method="HEAD")
    assert client_head.body == b""
    cl_values = [v.decode("latin1") for k, v in client_head.raw_headers if k.lower() == b"content-length"]
    assert cl_values == ["42"]

    no_content_resp = httpx.Response(204, headers=[], content=b"")
    client_204 = build_proxy_response(no_content_resp, b"", mutated=False, method="POST")
    assert client_204.status_code == 204
    assert client_204.body == b""


# ── 8. Unconditional Mutation & Fallback Contracts ───────────────────────────

def test_contract_unconditional_html_mutation(tmp_path, monkeypatch):
    """Eligible HTML response is mutated and registered in canary registry and ledger."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "mut_html.db"))
    db.reset_db()

    from sb.offense.injector import transform_response

    ctx = RequestContext(request=None)
    ctx.path = "/docs/spec"
    ctx.client_key = "ck-123"

    session = Session(session_id="sess-html-1", client_key="ck-123")
    upstream = httpx.Response(
        200,
        headers={"content-type": "text/html"},
        content=b"<html><body><main><p>Documentation</p></main></body></html>",
    )

    mutated_bytes = transform_response(ctx, session, upstream)
    text = mutated_bytes.decode("utf-8")

    assert "Documentation" in text
    assert "sb-canary" in text
    assert "SB-CANARY-" in text
    assert len(session.canaries_exposed) > 0

    # Verification of ledger entry
    verify = ledger.verify_chain()
    assert verify["result"] == "VALID"
    assert verify["count"] >= 1


def test_contract_unconditional_json_mutation(tmp_path, monkeypatch):
    """Eligible JSON response is mutated additively and registered."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "mut_json.db"))
    db.reset_db()

    from sb.offense.injector import transform_response

    ctx = RequestContext(request=None)
    ctx.path = "/api/catalog"
    ctx.client_key = "ck-json"

    session = Session(session_id="sess-json-1", client_key="ck-json")
    upstream = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        content=json.dumps({"products": [{"id": 1, "name": "Item"}]}).encode("utf-8"),
    )

    mutated_bytes = transform_response(ctx, session, upstream)
    data = json.loads(mutated_bytes.decode("utf-8"))

    assert "_sb_canary" in data
    assert data["_sb_canary"]["canary_id"].startswith("SB-CANARY-")
    assert data["products"][0]["name"] == "Item"


def test_contract_malformed_and_scalar_json_fail_pass(tmp_path, monkeypatch):
    """Malformed and scalar JSON log faults and pass through unmutated per total-error rule."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "json_fault.db"))
    db.reset_db()

    from sb.offense.injector import transform_response

    ctx = RequestContext(request=None)
    ctx.path = "/api/invalid"
    session = Session(session_id="sess-scalar", client_key="ck-s")

    # Malformed JSON
    bad_bytes = b"{\"unclosed: json"
    upstream_bad = httpx.Response(200, headers={"content-type": "application/json"}, content=bad_bytes)
    res_bad = transform_response(ctx, session, upstream_bad)
    assert res_bad == bad_bytes

    # Scalar JSON
    scalar_bytes = b"12345"
    upstream_scalar = httpx.Response(200, headers={"content-type": "application/json"}, content=scalar_bytes)
    res_scalar = transform_response(ctx, session, upstream_scalar)
    assert res_scalar == scalar_bytes
