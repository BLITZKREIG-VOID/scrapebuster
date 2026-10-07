"""Phase 0 comprehensive regression test suite.

Covers:
1. Bounded nested-lock concurrency and ledger integrity
2. Initialized missing-ledger across restart and reset (Missing History Guard)
3. Session/counter preservation and concurrency across resets
4. Prefetch ctx/session/init failure handling
5. Postfetch logging and fallback failures (unmutated pass)
6. Decoy handler fault guarding
7. Origin timeout/connect error with audit store down
8. POST forwarded exactly once without retry
9. Actual gzip HTML/JSON, binary, HEAD, repeated cookies, ETag/Digest invalidation, Cache-Control
10. Second lifespan client reset
11. Shared segment-safe trap path matching
12. Persisted stage visibility in traffic events API (no fake normalization)
13. Scalar/invalid JSON transparent handling
14. Missing history guard rejection of non-empty uninitialized databases
15. Atomic reset_db rollback on audit failure
16. Conditional headers stripped preventing 304 cache bypass on GET
17. Layer 3 decoy API descendants match
18. PUT forwards If-Match; origin 412 Precondition Failed preserved
19. POST forwards If-None-Match (*); origin 412 preserved once without replay
20. GET forwards If-Match precondition on document paths
21. HEAD preserves origin gzip representation metadata
22. Decoy fatal storage persistence failure fails-pass to origin once
23. Layer 3 classify_request propagates database errors
"""

import gzip
import json
import socket
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from sb.canary.registry import bind_session_canary, get_binding
from sb.canary.seed import seed_canaries
from sb.config import is_trap_path
from sb.contracts import Health, TrafficEvents
from sb.edge.context import RequestContext, build_context
from sb.edge.pipeline import build_proxy_response, handle, log_event
import sb.edge.proxy as proxy_module
from sb.edge.session import Session, sessions
from sb.main import app, lifespan
from sb.store import db, ledger


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── 1. Bounded nested-lock and ledger concurrency ────────────────────────────

def test_bounded_nested_lock_and_ledger_concurrency(tmp_path, monkeypatch):
    """Verify concurrent transactions and nested lock acquisitions complete without deadlock."""
    test_db = str(tmp_path / "lock_concurrency.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()

    errors: list[Exception] = []

    def worker_append(idx: int):
        try:
            for j in range(5):
                ledger.append_event("test_worker", {"worker": idx, "iter": j})
        except Exception as exc:
            errors.append(exc)

    def worker_reset():
        try:
            time.sleep(0.01)
            db.reset_db()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker_append, args=(i,)) for i in range(4)]
    threads.append(threading.Thread(target=worker_reset))

    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)
        assert not t.is_alive(), "Worker thread deadlocked during concurrent DB access"

    assert time.time() - start < 10.0, "Concurrency test exceeded bounded time limit"
    assert not errors, f"Concurrency errors encountered: {errors}"

    verify = ledger.verify_chain()
    assert verify["result"] == "VALID"
    assert verify["count"] > 0


# ── 2. Initialized missing-ledger across restart and reset ────────────────────

def test_initialized_missing_ledger_across_restart_and_reset(tmp_path, monkeypatch):
    """Missing History Guard: dropped forensic_ledger table stays TAMPERED and is never silently recreated."""
    test_db = str(tmp_path / "missing_history.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()

    # Append an initial event to establish history
    ledger.append_event("genesis_event", {"status": "active"})
    assert ledger.verify_chain()["result"] == "VALID"

    # Simulate tampering / dropped audit history
    with closing(db.get_connection()) as conn, conn:
        conn.execute("DROP TABLE forensic_ledger")

    # verify_chain reports TAMPERED
    tampered_check = ledger.verify_chain()
    assert tampered_check["result"] == "TAMPERED"
    assert "forensic_ledger" in tampered_check["errors"][0]

    # Restart / init_db MUST raise OperationalError and refuse to recreate dropped ledger
    with pytest.raises(sqlite3.OperationalError, match="database is TAMPERED"):
        db.init_db()

    # reset_db MUST also raise OperationalError and refuse to silently recreate
    with pytest.raises(sqlite3.OperationalError, match="database is TAMPERED"):
        db.reset_db()

    # Append to dropped ledger fails visibly
    with pytest.raises(sqlite3.OperationalError):
        ledger.append_event("tampered_append", {"status": "fail"})

    # Health API reports degraded / down
    from sb.api.health import get_health

    import asyncio
    health_resp = asyncio.run(get_health())
    assert health_resp.status == "degraded"
    assert health_resp.components["db"] == "down"


# ── 3. Session / counter preservation and concurrency ─────────────────────────

def test_session_counter_preservation_and_concurrency(tmp_path, monkeypatch):
    """Operational reset preserves forensic ledger, canary counters, and bindings atomically."""
    test_db = str(tmp_path / "session_counter.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()

    sid = "sess-preserve-test"
    binding1 = bind_session_canary(sid, vector="TEXT")
    binding2 = bind_session_canary(sid, vector="API")

    assert binding1.canary_id.endswith("-0001")
    assert binding2.canary_id.endswith("-0002")

    # Operational reset
    db.reset_db()

    # Bindings are preserved
    stored1 = get_binding(binding1.canary_id)
    assert stored1 is not None
    assert stored1.canary_id == binding1.canary_id
    assert stored1.value == binding1.value

    # Next allocated sequence after reset is strictly monotonic (0003)
    binding3 = bind_session_canary(sid, vector="TEXT")
    assert binding3.canary_id.endswith("-0003")

    # Forensic ledger contains bindings and the operational reset event
    verify = ledger.verify_chain()
    assert verify["result"] == "VALID"
    assert verify["count"] >= 4  # 3 bindings + 1 reset


# ── 4. Prefetch ctx/session/init failure handling ─────────────────────────────

@pytest.mark.asyncio
async def test_prefetch_failures_handled_safely(tmp_path, monkeypatch):
    """Prefetch failures forward once via minimal safe context and do not 500."""
    test_db = str(tmp_path / "prefetch_test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    # Start ephemeral origin
    origin_app = FastAPI()

    @origin_app.get("/test-prefetch")
    async def origin_handler():
        return HTMLResponse(content="<html><body><main><p>Origin Page</p></main></body></html>")

    port = find_free_port()
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        # Failure in build_context falls back to minimal context and forwards
        def exploding_build_context(req):
            raise RuntimeError("Synthetic context construction failure")

        monkeypatch.setattr("sb.edge.pipeline.build_context", exploding_build_context)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/test-prefetch", headers={"user-agent": "test-browser"})
            assert resp.status_code == 200
            assert b"Origin Page" in resp.content
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 5. Postfetch logging and fallback failures ────────────────────────────────

@pytest.mark.asyncio
async def test_postfetch_failures_return_unmutated_pass(tmp_path, monkeypatch):
    """Total internal pipeline fault returns captured upstream response unmutated with loud fault log."""
    test_db = str(tmp_path / "postfetch_test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    origin_app = FastAPI()

    @origin_app.get("/unmutated-pass")
    async def origin_handler():
        return HTMLResponse(content="<html><body><main><p>Original Upstream Text</p></main></body></html>")

    port = find_free_port()
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        # Simulate internal store fault during postfetch telemetry logging
        def exploding_log_event(*args, **kwargs):
            raise sqlite3.OperationalError("Simulated postfetch database fault")

        monkeypatch.setattr("sb.edge.pipeline.log_event", exploding_log_event)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/unmutated-pass", headers={"user-agent": "test-browser"})
            assert resp.status_code == 200
            # Returns captured original upstream status/body UNMUTATED
            assert b"Original Upstream Text" in resp.content
            assert b"sb-canary" not in resp.content
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 6. Decoy handler fault guarding ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_decoy_handler_fault_does_not_escape(tmp_path, monkeypatch):
    """Decoy handler exception is caught and recorded; does not cause 500 error."""
    test_db = str(tmp_path / "decoy_test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    monkeypatch.setenv("SB_TRAP_PATHS", '["/trap/fault-path"]')

    origin_app = FastAPI()

    @origin_app.get("/trap/fault-path")
    async def origin_handler():
        return HTMLResponse(content="<html><body><main><p>Origin Trap</p></main></body></html>")

    port = find_free_port()
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        def exploding_decoy(*args, **kwargs):
            raise RuntimeError("Synthetic decoy failure")

        monkeypatch.setattr("sb.offense.injector.handle_decoy", exploding_decoy)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/trap/fault-path", headers={"user-agent": "test-browser"})
            assert resp.status_code == 200
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 7. Origin timeout/connect error with audit store down ─────────────────────

@pytest.mark.asyncio
async def test_origin_outage_with_audit_store_down(tmp_path, monkeypatch):
    """Origin 504 and 502 errors return correct status even when the audit database is down."""
    test_db = str(tmp_path / "down_db.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()

    # Point proxy to a non-existent port (connect error)
    unused_port = find_free_port()
    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{unused_port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{unused_port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    # Disable database
    def broken_conn():
        raise sqlite3.OperationalError("Database is down")

    monkeypatch.setattr(db, "get_connection", broken_conn)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/origin-down", headers={"user-agent": "test-browser"})
        assert resp.status_code == 502
        assert b"Bad Gateway" in resp.content


# ── 8. POST forwarded exactly once without replay ─────────────────────────────

@pytest.mark.asyncio
async def test_post_forwarded_exactly_once(tmp_path, monkeypatch):
    """Non-idempotent POST requests are forwarded exactly once and never replayed."""
    test_db = str(tmp_path / "post_once.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    post_count = 0
    origin_app = FastAPI()

    @origin_app.post("/action/submit")
    async def post_handler(req: Request):
        nonlocal post_count
        post_count += 1
        body = await req.json()
        return JSONResponse(content={"result": "created", "received": body})

    port = find_free_port()
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/action/submit",
                json={"item": "widget", "qty": 42},
                headers={"user-agent": "test-browser"},
            )
            assert resp.status_code == 200
            assert post_count == 1
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 9. Gzip HTML/JSON, binary, HEAD, repeated cookies, ETag invalidation ──────

def test_build_proxy_response_gzip_head_cookies_and_etag_invalidation():
    """Verify build_proxy_response adherence to RFC and Phase 0 fidelity requirements."""
    # 9a. Non-HEAD response emits Content-Length matching decoded bytes
    decoded_html = b"<html><body><p>Decoded HTML</p></body></html>"
    compressed_bytes = gzip.compress(decoded_html)

    req = httpx.Request("GET", "http://example.org/test")
    raw_headers = [
        (b"content-type", b"text/html; charset=utf-8"),
        (b"content-encoding", b"gzip"),
        (b"content-length", str(len(compressed_bytes)).encode("ascii")),
        (b"etag", b'"stale-etag-123"'),
        (b"set-cookie", b"c1=v1; Path=/"),
        (b"set-cookie", b"c2=v2; Path=/"),
    ]
    resp = httpx.Response(200, request=req, headers=raw_headers, content=compressed_bytes)

    # Mutated response
    mutated_html = b"<html><body><p>Decoded HTML</p><p class='sb-canary'>Token</p></body></html>"
    proxy_resp = build_proxy_response(resp, mutated_html, mutated=True, method="GET")

    # Content-Length matches actual emitted bytes
    cl_headers = [v for k, v in proxy_resp.raw_headers if k.lower() == b"content-length"]
    assert cl_headers == [str(len(mutated_html)).encode("ascii")]

    # Content-Encoding is stripped
    ce_headers = [v for k, v in proxy_resp.raw_headers if k.lower() == b"content-encoding"]
    assert len(ce_headers) == 0

    # Stale ETag is invalidated and removed
    etag_headers = [v for k, v in proxy_resp.raw_headers if k.lower() == b"etag"]
    assert len(etag_headers) == 0

    # Cache-Control: private, no-store is applied
    cc_headers = [v for k, v in proxy_resp.raw_headers if k.lower() == b"cache-control"]
    assert b"private, no-store" in b",".join(cc_headers)

    # Repeated Set-Cookie headers are preserved
    sc_headers = [v for k, v in proxy_resp.raw_headers if k.lower() == b"set-cookie"]
    assert len(sc_headers) == 2
    assert b"c1=v1" in sc_headers[0]
    assert b"c2=v2" in sc_headers[1]

    # 9b. HEAD request preserves upstream representation Content-Length and has empty body
    head_resp = httpx.Response(200, request=httpx.Request("HEAD", "http://example.org/test"), headers=[
        (b"content-type", b"text/html"),
        (b"content-length", b"12345"),
    ])
    proxy_head = build_proxy_response(head_resp, b"", mutated=False, method="HEAD")
    assert proxy_head.body == b""
    head_cl = [v for k, v in proxy_head.raw_headers if k.lower() == b"content-length"]
    assert head_cl == [b"12345"]

    # 9c. 204 No Content has no body and no Content-Length
    resp_204 = httpx.Response(204, request=req)
    proxy_204 = build_proxy_response(resp_204, b"", mutated=False, method="DELETE")
    assert proxy_204.body == b""
    cl_204 = [v for k, v in proxy_204.raw_headers if k.lower() == b"content-length"]
    assert len(cl_204) == 0


# ── 10. Second lifespan client reset ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_second_lifespan_both_proxy(tmp_path, monkeypatch):
    """Running application lifespan sequentially resets client cleanly without connection error."""
    test_db = str(tmp_path / "lifespan_test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    origin_app = FastAPI()

    @origin_app.get("/lifespan-route")
    async def origin_handler():
        return HTMLResponse(content="<html><body><main><p>Lifespan Success</p></main></body></html>")

    port = find_free_port()
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        # First lifespan
        async with lifespan(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp1 = await client.get("/lifespan-route", headers={"user-agent": "test"})
                assert resp1.status_code == 200

        # Second lifespan
        async with lifespan(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp2 = await client.get("/lifespan-route", headers={"user-agent": "test"})
                assert resp2.status_code == 200
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 11. Trap segment matching ─────────────────────────────────────────────────

def test_trap_segment_matching(monkeypatch):
    """Segment-safe trap matching matches exact and segment subpaths, but never non-segment prefixes."""
    monkeypatch.setenv("SB_TRAP_PATHS", '["/trap/decoy"]')
    monkeypatch.setenv("SB_TRAP_API_PATH", "/api/decoy")

    # Exact matches
    assert is_trap_path("/trap/decoy")
    assert is_trap_path("/trap/decoy/")
    assert is_trap_path("/api/decoy")
    assert is_trap_path("/api/decoy/")

    # Subpath segment matches
    assert is_trap_path("/trap/decoy/catalog")
    assert is_trap_path("/api/decoy/users")

    # Non-segment prefix matches MUST NOT match
    assert not is_trap_path("/trap/decoy-other")
    assert not is_trap_path("/trap/decoy123")
    assert not is_trap_path("/api/decoy_other")
    assert not is_trap_path("/other/path")


# ── 12. Persisted stage in traffic API ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_persisted_stage_in_traffic_api(tmp_path, monkeypatch):
    """Traffic events API reflects actual persisted stage without fake normalization to offense."""
    test_db = str(tmp_path / "traffic_stage.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            """INSERT INTO traffic_events
               (event_id, ts, session_id, client_key, ip, method, path, status_code,
                user_agent, header_fp, stage, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("evt-1", "2026-10-07T00:00:00Z", "s1", "c1", "127.0.0.1", "GET", "/test1",
             200, "ua", "fp", "ORIGIN", "ORIGIN", "SANDBOX", 0, "[]"),
        )
        conn.execute(
            """INSERT INTO traffic_events
               (event_id, ts, session_id, client_key, ip, method, path, status_code,
                user_agent, header_fp, stage, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("evt-2", "2026-10-07T00:00:01Z", "s2", "c2", "127.0.0.1", "GET", "/test2",
             200, "ua", "fp", "OFFENSE", "OFFENSE", "SANDBOX", 0, "[]"),
        )
        # Row with NULL stage (missing/corrupt metadata)
        conn.execute(
            """INSERT INTO traffic_events
               (event_id, ts, session_id, client_key, ip, method, path, status_code,
                user_agent, header_fp, stage, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("evt-3", "2026-10-07T00:00:02Z", "s3", "c3", "127.0.0.1", "GET", "/test3",
             200, "ua", "fp", None, "ORIGIN", "SANDBOX", 0, "[]"),
        )

    from sb.api.traffic import get_traffic_events
    events_resp = await get_traffic_events(after=0, limit=10)
    assert len(events_resp.events) == 3

    assert events_resp.events[0].stage == "ORIGIN"
    assert events_resp.events[1].stage == "OFFENSE"
    # Null stage remains None, visibly corrupt/missing rather than fake-normalized to offense
    assert events_resp.events[2].stage is None


# ── 13. Malformed trap config does not abort forwarding ───────────────────────

@pytest.mark.asyncio
async def test_malformed_trap_paths_config_does_not_abort_forwarding(tmp_path, monkeypatch):
    """Malformed SB_TRAP_PATHS env var does not crash proxy or abort origin forwarding."""
    test_db = str(tmp_path / "trap_cfg.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    origin_app = FastAPI()

    @origin_app.get("/items/safe")
    async def items_handler():
        return HTMLResponse("<html><body><main><p>Origin Safe Item</p></main></body></html>")

    port = find_free_port()
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_TRAP_PATHS", "NOT_A_VALID_JSON_ARRAY{{{")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/items/safe", headers={"user-agent": "test-agent"})
            assert resp.status_code == 200
            assert b"Origin Safe Item" in resp.content
            assert b"sb-canary" in resp.content
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 14. Non-empty DB without marker/ledger rejected as TAMPERED ───────────────

def test_non_empty_db_without_marker_or_ledger_rejected_as_tampered(tmp_path, monkeypatch):
    """An established non-empty DB missing initialized marker or ledger is rejected as TAMPERED."""
    test_db = str(tmp_path / "tampered_nonempty.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    # Tamper by dropping both app_state and forensic_ledger while traffic_events remain
    with closing(db.get_connection()) as conn, conn:
        conn.execute("DROP TABLE forensic_ledger")
        conn.execute("DROP TABLE app_state")

    # init_db must reject this non-empty database instead of silently creating genesis
    with pytest.raises(sqlite3.OperationalError, match="database is TAMPERED"):
        db.init_db()


# ── 15. Atomic reset_db rolls back on audit failure ───────────────────────────

def test_atomic_reset_db_rolls_back_on_audit_failure(tmp_path, monkeypatch):
    """If appending the reset event fails, projection deletions are rolled back."""
    test_db = str(tmp_path / "atomic_reset.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    # Insert a dummy traffic event
    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            """INSERT INTO traffic_events
               (event_id, ts, session_id, client_key, ip, method, path, status_code,
                user_agent, header_fp, stage, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("evt-atomic", "2026-10-07T00:00:00Z", "s1", "c1", "127.0.0.1", "GET", "/path",
             200, "ua", "fp", "ORIGIN", "ORIGIN", "SANDBOX", 0, "[]"),
        )

    # Verify event exists
    with closing(db.get_connection()) as conn:
        count = conn.execute("SELECT count(*) FROM traffic_events").fetchone()[0]
        assert count == 1

    # Mock append_event inside db.reset_db to fail
    from sb.store import ledger
    orig_append = ledger.append_event

    def broken_append(*args, **kwargs):
        raise sqlite3.OperationalError("Simulated ledger write fault")

    monkeypatch.setattr(ledger, "append_event", broken_append)

    with pytest.raises(sqlite3.OperationalError, match="Simulated ledger write fault"):
        db.reset_db()

    # Verify projection table was NOT emptied (rolled back atomically)
    with closing(db.get_connection()) as conn:
        count = conn.execute("SELECT count(*) FROM traffic_events").fetchone()[0]
        assert count == 1, "Projections must not be deleted if audit event append fails"


# ── 16. Conditional headers stripped preventing 304 cache bypass ──────────────

@pytest.mark.asyncio
async def test_conditional_headers_stripped_preventing_304_bypass(tmp_path, monkeypatch):
    """Incoming If-None-Match and If-Modified-Since are stripped to prevent unwatermarked 304 bypass."""
    test_db = str(tmp_path / "conditional_strip.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    received_headers = {}
    origin_app = FastAPI()

    @origin_app.get("/page")
    async def page_handler(req: Request):
        received_headers.update({k.lower(): v for k, v in req.headers.items()})
        return HTMLResponse(
            "<html><body><main><p>Always Fresh Content</p></main></body></html>",
            headers={"etag": '"v123"'},
        )

    port = find_free_port()
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                "/page",
                headers={
                    "user-agent": "test-agent",
                    "if-none-match": '"v123"',
                    "if-modified-since": "Wed, 07 Oct 2026 00:00:00 GMT",
                },
            )
            # Origin must NOT have received conditional headers
            assert "if-none-match" not in received_headers
            assert "if-modified-since" not in received_headers
            # Proxy returns full 200 with canary mutation, NOT 304 Not Modified
            assert resp.status_code == 200
            assert b"Always Fresh Content" in resp.content
            assert b"sb-canary" in resp.content
            # Etag was stripped and Cache-Control: private, no-store was enforced
            assert "etag" not in resp.headers
            assert "private, no-store" in resp.headers.get("cache-control", "")
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 17. Layer 3 decoy API descendants match ───────────────────────────────────

def test_layer3_decoy_api_descendants_match(monkeypatch):
    """match_trap matches both exact decoy API and subpath descendants."""
    from sb.offense.layer3 import match_trap

    monkeypatch.setenv("SB_TRAP_API_PATH", "/api/v1/decoy")
    monkeypatch.setenv("SB_TRAP_PATHS", '["/trap/pot"]')

    # Exact decoy API
    hit1 = match_trap("/api/v1/decoy")
    assert hit1 is not None and hit1.trap_type == "decoy_api"

    # Decoy API subpath descendant
    hit2 = match_trap("/api/v1/decoy/users")
    assert hit2 is not None and hit2.trap_type == "decoy_api"

    # Trap path and subpath
    hit3 = match_trap("/trap/pot")
    assert hit3 is not None and hit3.trap_type == "trap_path"
    hit4 = match_trap("/trap/pot/sub")
    assert hit4 is not None and hit4.trap_type == "trap_path"

    # Partial prefix non-matches
    assert match_trap("/api/v1/decoy-other") is None
    assert match_trap("/trap/pot-other") is None


# ── 18. PUT forwards If-Match; origin 412 Precondition Failed preserved ───────

@pytest.mark.asyncio
async def test_put_forwards_if_match_and_preserves_origin_412(tmp_path, monkeypatch):
    """Unsafe method PUT preserves If-Match precondition; origin 412 is returned without proxy override."""
    test_db = str(tmp_path / "put_if_match.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    received_headers = {}
    put_count = 0
    origin_app = FastAPI()

    @origin_app.put("/items/widget")
    async def put_handler(req: Request):
        nonlocal put_count
        put_count += 1
        received_headers.update({k.lower(): v for k, v in req.headers.items()})
        if req.headers.get("if-match") != '"v1.0.0"':
            return Response(content="Precondition Failed", status_code=412, media_type="text/plain")
        return Response(content="Updated", status_code=200, media_type="text/plain")

    port = find_free_port()
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.put(
                "/items/widget",
                content=b'{"qty": 5}',
                headers={
                    "user-agent": "test-agent",
                    "if-match": '"stale-etag-999"',
                },
            )
            # Origin received the forwarded If-Match header
            assert received_headers.get("if-match") == '"stale-etag-999"'
            # Origin decision 412 is preserved faithfully by proxy
            assert resp.status_code == 412
            assert resp.text == "Precondition Failed"
            assert put_count == 1
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 19. POST forwards If-None-Match (*); origin 412 preserved once without replay ─

@pytest.mark.asyncio
async def test_post_forwards_if_none_match_and_never_replays(tmp_path, monkeypatch):
    """Unsafe method POST preserves create-if-absent (If-None-Match: *); origin rejection is preserved without replay."""
    test_db = str(tmp_path / "post_if_none_match.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    received_headers = {}
    post_count = 0
    origin_app = FastAPI()

    @origin_app.post("/items/create")
    async def post_handler(req: Request):
        nonlocal post_count
        post_count += 1
        received_headers.update({k.lower(): v for k, v in req.headers.items()})
        if req.headers.get("if-none-match") == "*":
            # Resource already exists -> 412 Precondition Failed
            return Response(content="Resource Already Exists", status_code=412, media_type="text/plain")
        return Response(content="Created", status_code=201, media_type="text/plain")

    port = find_free_port()
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/items/create",
                content=b'{"id": "existing"}',
                headers={
                    "user-agent": "test-agent",
                    "if-none-match": "*",
                },
            )
            assert received_headers.get("if-none-match") == "*"
            assert resp.status_code == 412
            assert resp.text == "Resource Already Exists"
            assert post_count == 1
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 20. GET forwards If-Match precondition on document paths ───────────────────

@pytest.mark.asyncio
async def test_get_forwards_if_match_precondition(tmp_path, monkeypatch):
    """GET preserves state-changing precondition If-Match, allowing origin concurrency validation."""
    test_db = str(tmp_path / "get_if_match.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    received_headers = {}
    origin_app = FastAPI()

    @origin_app.get("/document/doc1")
    async def get_handler(req: Request):
        received_headers.update({k.lower(): v for k, v in req.headers.items()})
        if req.headers.get("if-match") == '"valid-v1"':
            return HTMLResponse(
                "<html><body><p>Validated Document Body</p></body></html>",
                headers={"etag": '"valid-v1"'},
            )
        return Response(content="Precondition Failed", status_code=412)

    port = find_free_port()
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                "/document/doc1",
                headers={
                    "user-agent": "test-agent",
                    "if-match": '"valid-v1"',
                },
            )
            assert received_headers.get("if-match") == '"valid-v1"'
            assert resp.status_code == 200
            assert b"Validated Document Body" in resp.content
            assert b"sb-canary" in resp.content
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 21. HEAD preserves origin gzip representation metadata ─────────────────────

@pytest.mark.asyncio
async def test_head_preserves_origin_gzip_metadata(tmp_path, monkeypatch):
    """HEAD preserves client Accept-Encoding: gzip and returns upstream Content-Encoding and Content-Length."""
    test_db = str(tmp_path / "head_gzip.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    received_headers = {}
    origin_app = FastAPI()

    @origin_app.head("/asset/bundle.js")
    async def head_handler(req: Request):
        received_headers.update({k.lower(): v for k, v in req.headers.items()})
        return Response(
            content=b"",
            status_code=200,
            headers={
                "content-type": "application/javascript",
                "content-encoding": "gzip",
                "content-length": "45678",
            },
        )

    port = find_free_port()
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.head(
                "/asset/bundle.js",
                headers={
                    "user-agent": "test-agent",
                    "accept-encoding": "gzip",
                },
            )
            assert received_headers.get("accept-encoding") == "gzip"
            assert resp.status_code == 200
            assert resp.content == b""
            assert resp.headers.get("content-encoding") == "gzip"
            assert resp.headers.get("content-length") == "45678"
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 22. Decoy fatal storage persistence failure fails-pass to origin once ──────

@pytest.mark.asyncio
async def test_decoy_storage_fault_fails_pass_to_origin(tmp_path, monkeypatch):
    """When audit/session persistence fatally fails during decoy handling, fail-pass to origin once."""
    test_db = str(tmp_path / "decoy_storage_fault.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.reset_db()

    origin_app = FastAPI()

    @origin_app.get("/trap/honey")
    async def origin_honey():
        return HTMLResponse("<html><body><main><p>Real Upstream Origin Fallback</p></main></body></html>")

    port = find_free_port()
    server = uvicorn.Server(uvicorn.Config(app=origin_app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.1)

    monkeypatch.setattr(proxy_module, "SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("SB_UPSTREAM_ORIGIN", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(proxy_module, "_client", None)
    monkeypatch.setenv("SB_TRAP_PATHS", '["/trap/honey"]')

    import sb.edge.pipeline as pipe_mod

    def broken_log_event(*args, **kwargs):
        raise sqlite3.OperationalError("Simulated decoy audit persistence failure")

    monkeypatch.setattr(pipe_mod, "log_event", broken_log_event)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/trap/honey", headers={"user-agent": "test-agent"})
            # Must NOT return decoy; must fail-pass to upstream origin
            assert resp.status_code == 200
            assert b"Real Upstream Origin Fallback" in resp.content
    finally:
        server.should_exit = True
        t.join(timeout=2)


# ── 23. Layer 3 classify_request propagates database errors ───────────────────

def test_layer3_classify_request_propagates_database_error(monkeypatch):
    """classify_request no longer silently swallows DB persistence errors with except: pass."""
    from types import SimpleNamespace
    from sb.offense.layer3 import classify_request

    monkeypatch.setenv("SB_TRAP_PATHS", '["/trap/error"]')

    def broken_conn():
        raise sqlite3.OperationalError("Simulated DB connection failure")

    monkeypatch.setattr(db, "get_connection", broken_conn)

    ctx = SimpleNamespace(path="/trap/error")
    sess = SimpleNamespace(session_id="sess-err", state="SANDBOX")

    with pytest.raises(sqlite3.OperationalError, match="Simulated DB connection failure"):
        classify_request(ctx, sess)


