"""Edge pipeline — request decision flow for Phase0.

Pipeline: context -> session -> telemetry/decoy -> upstream-fetch -> unconditional-mutation -> response.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Request, Response

from ..config import is_trap_path
from ..store.db import get_connection
from ..store.ledger import append_event
from ..store.sessions import save_session
from .context import RequestContext, build_context
from .intel import init_request, record_decision
from .proxy import HOP_BY_HOP_HEADERS, UpstreamResponse, proxy
from .session import Session, sessions

logger = logging.getLogger("sb.edge.pipeline")

TRAFFIC_STAGES = frozenset({"OFFENSE", "ORIGIN"})
TRAFFIC_LAYERS = TRAFFIC_STAGES  # Alias for backward compatibility
TRAFFIC_DECISIONS = frozenset({
    "FAST_PATH",
    "SANDBOX",
})


def _build_minimal_context(request: Request) -> RequestContext:
    """Build safe minimal request context when standard context construction fails."""
    try:
        return RequestContext(request)
    except Exception:
        ctx = RequestContext.__new__(RequestContext)
        ctx.request = request
        ctx.ip = getattr(getattr(request, "client", None), "host", "127.0.0.1") or "127.0.0.1"
        ctx.user_agent = request.headers.get("user-agent", "") if getattr(request, "headers", None) else ""
        ctx.path = getattr(getattr(request, "url", None), "path", "/") or "/"
        ctx.client_key = "minimal-client-key"
        ctx.header_fp = "minimal-header-fp"
        ctx.is_document = False
        return ctx


def _build_minimal_session(ctx: RequestContext) -> Session:
    """Build safe in-memory fallback session when session lookup/creation fails."""
    sid = f"fallback-{uuid.uuid4().hex[:12]}"
    return Session(session_id=sid, client_key=getattr(ctx, "client_key", "fallback"))


def _get_offense_hooks():
    """Resolve offense hooks directly from sb.hooks or sb.offense."""
    try:
        from sb.hooks import offense_hooks

        if offense_hooks is not None:
            return offense_hooks.handle_decoy, offense_hooks.transform_response
    except Exception as exc:
        logger.warning("Could not resolve offense_hooks from sb.hooks: %s", exc)

    try:
        from sb.offense.injector import handle_decoy, transform_response

        return handle_decoy, transform_response
    except ImportError as exc:
        logger.error("sb.offense hooks unavailable: %s", exc)
        return None, None


def _append_fault_record(record: dict[str, Any]) -> None:
    """Append fault record to durable store and ledger without unchained silent failure."""
    try:
        append_event("fault", record)
    except Exception as exc:
        logger.error("Failed to append fault event to ledger: %s", exc)


def is_eligible_for_mutation(method: str, status_code: int, content_type: str) -> bool:
    """Return True if response is eligible for sandboxed offensive mutation."""
    if method.upper() in {"HEAD", "OPTIONS"}:
        return False
    if status_code in {204, 205, 304}:
        return False
    ct = content_type.lower()
    return "text/html" in ct or "application/xhtml+xml" in ct or "application/json" in ct or "+json" in ct


def build_proxy_response(
    upstream: httpx.Response,
    body: bytes,
    mutated: bool,
    method: str,
) -> Response:
    """Build FastAPI Response from upstream httpx.Response.

    Preserves repeated headers (especially origin Set-Cookie),
    strips hop-by-hop and Connection-nominated headers,
    preserves upstream HEAD Content-Length representation metadata without body,
    emits Content-Length matching actual body bytes for non-HEAD responses,
    invalidates stale representation validators and digests (ETag, Content-MD5, Digest,
    Content-Digest, Repr-Digest) on mutation, and applies Cache-Control: private, no-store
    to prevent shared cache leakage.
    Safe for HEAD, binary, 204, and 304 responses.
    """
    status_code = upstream.status_code
    method_upper = method.upper()
    is_head = method_upper == "HEAD"
    is_empty_status = status_code in (204, 205, 304)

    if is_head or is_empty_status:
        resp_body = b""
    else:
        resp_body = body

    resp = Response(content=resp_body, status_code=status_code)

    # Connection-nominated headers to strip
    connection_tokens = set()
    conn_hdr = upstream.headers.get("connection", "")
    if conn_hdr:
        for token in conn_hdr.split(","):
            t = token.strip().lower()
            if t:
                connection_tokens.add(t)

    drop_headers = set(HOP_BY_HOP_HEADERS) | connection_tokens

    if not is_head:
        # For non-HEAD, httpx decompresses wire body; strip content-encoding and stale digests
        drop_headers.add("content-encoding")
        drop_headers |= {"digest", "content-digest", "repr-digest"}

    if mutated:
        # Invalidate stale validators, representation digests, caching, and range headers on mutation
        drop_headers |= {
            "etag",
            "content-md5",
            "digest",
            "content-digest",
            "repr-digest",
            "cache-control",
            "last-modified",
            "content-range",
        }

    raw_headers: list[tuple[bytes, bytes]] = []

    for k_bytes, v_bytes in upstream.headers.raw:
        k_lower = k_bytes.lower().decode("latin1", errors="replace")
        if k_lower in drop_headers:
            continue
        if k_lower == "content-length":
            if is_head:
                # Preserve upstream HEAD Content-Length representation metadata
                raw_headers.append((k_bytes, v_bytes))
            # For non-HEAD, do not copy upstream Content-Length; we emit exact byte count below
            continue
        if mutated and k_lower == "content-type" and b"text/html" in v_bytes.lower():
            # Ensure HTML representation metadata indicates UTF-8 encoding matching injected watermarks
            raw_headers.append((b"content-type", b"text/html; charset=utf-8"))
            continue
        raw_headers.append((k_bytes, v_bytes))

    # Add exact Content-Length matching actual bytes for non-HEAD responses with bodies
    if not is_head and not is_empty_status:
        raw_headers.append((b"content-length", str(len(resp_body)).encode("ascii")))

    if mutated:
        # Prevent shared cache leakage of per-session mutations
        raw_headers.append((b"cache-control", b"private, no-store"))

    resp.raw_headers = raw_headers
    return resp


def log_event(
    ctx: RequestContext,
    session: Session,
    stage: str,
    decision: str,
    status_code: int,
    reasons: list[str] | None = None,
    risk_score: int | None = None,
    layer: str | None = None,
) -> None:
    """Log a traffic event to database and append to forensic ledger."""
    if reasons is None:
        reasons = []

    actual_stage = stage or layer or "ORIGIN"
    actual_layer = layer or actual_stage

    if actual_stage not in TRAFFIC_STAGES and actual_stage not in TRAFFIC_LAYERS:
        raise ValueError(f"Unsupported traffic stage/layer: {actual_stage}")
    if decision not in TRAFFIC_DECISIONS:
        raise ValueError(f"Unsupported traffic decision: {decision}")

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event_id = f"evt-{uuid.uuid4().hex[:8]}"

    if session is not None and event_id not in session.event_ids:
        session.event_ids.append(event_id)
    if session is not None and reasons:
        for r in reasons:
            if r not in session.reasons:
                session.reasons.append(r)

    session_id = getattr(session, "session_id", "unknown") if session else "unknown"
    client_key = getattr(ctx, "client_key", "") if ctx else ""
    ip = getattr(ctx, "ip", "127.0.0.1") if ctx else "127.0.0.1"
    method = ctx.request.method if ctx and getattr(ctx, "request", None) else "GET"
    path = getattr(ctx, "path", "/") if ctx else "/"
    user_agent = getattr(ctx, "user_agent", "") if ctx else ""
    header_fp = getattr(ctx, "header_fp", "") if ctx else ""

    db_failed = False
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO traffic_events
               (event_id, ts, session_id, client_key, ip, method, path, status_code,
                user_agent, header_fp, stage, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                ts,
                session_id,
                client_key,
                ip,
                method,
                path,
                status_code,
                user_agent,
                header_fp,
                actual_stage,
                actual_layer,
                decision,
                0 if risk_score is None else risk_score,
                json.dumps(reasons),
            ),
        )
        conn.commit()
    except Exception as db_err:
        logger.error("Failed to insert traffic_event: %s", db_err)
        db_failed = True
    finally:
        conn.close()

    record = {
        "event_id": event_id,
        "session_id": session_id,
        "client_key": client_key,
        "ip": ip,
        "method": method,
        "path": path,
        "status_code": status_code,
        "user_agent": user_agent,
        "header_fp": header_fp,
        "stage": actual_stage,
        "layer": actual_layer,
        "decision": decision,
        "risk_score": 0 if risk_score is None else risk_score,
        "reasons": reasons,
        "ts": ts,
    }
    ledger_failed = False
    try:
        append_event("traffic", record)
    except Exception as ledger_err:
        logger.error("Failed to append traffic event to ledger: %s", ledger_err)
        ledger_failed = True

    if db_failed or ledger_failed:
        raise sqlite3.OperationalError(
            f"Audit store persistence fault: db_ok={not db_failed}, ledger_ok={not ledger_failed}"
        )


async def handle(request: Request) -> Response:
    """Handle an incoming request through the guarded edge pipeline."""
    # Guard prefetch context and session creation
    try:
        ctx = build_context(request)
    except Exception as ctx_err:
        logger.error("Prefetch build_context failed for %s: %s", getattr(request, "url", "/"), ctx_err)
        ctx = _build_minimal_context(request)
        _append_fault_record({
            "event_type": "prefetch_context_fault",
            "path": getattr(ctx, "path", "/"),
            "error": str(ctx_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    try:
        session = sessions.get_or_create(ctx)
    except Exception as sess_err:
        logger.error("Prefetch sessions.get_or_create failed for %s: %s", getattr(ctx, "path", "/"), sess_err)
        session = _build_minimal_session(ctx)
        _append_fault_record({
            "event_type": "prefetch_session_fault",
            "session_id": getattr(session, "session_id", "unknown"),
            "path": getattr(ctx, "path", "/"),
            "error": str(sess_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    try:
        init_request(ctx, session)
    except Exception as init_err:
        logger.error("Prefetch init_request failed for %s: %s", getattr(ctx, "path", "/"), init_err)
        _append_fault_record({
            "event_type": "prefetch_init_fault",
            "session_id": getattr(session, "session_id", "unknown"),
            "path": getattr(ctx, "path", "/"),
            "error": str(init_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    try:
        save_session(session)
    except Exception as sess_err:
        logger.error("Failed to save session before fetch: %s", sess_err)
        _append_fault_record({
            "event_type": "pre_fetch_session_save_error",
            "session_id": getattr(session, "session_id", "unknown"),
            "client_key": getattr(ctx, "client_key", ""),
            "path": getattr(ctx, "path", "/"),
            "error": str(sess_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    try:
        return await _handle_request(ctx, session)
    finally:
        try:
            save_session(session)
        except Exception as sess_err:
            logger.error("Failed to save session in finally: %s", sess_err)
            _append_fault_record({
                "event_type": "post_fetch_session_save_error",
                "session_id": getattr(session, "session_id", "unknown"),
                "client_key": getattr(ctx, "client_key", ""),
                "path": getattr(ctx, "path", "/"),
                "error": str(sess_err),
                "ts": datetime.now(timezone.utc).isoformat(),
            })


async def _handle_request(ctx: RequestContext, session: Session) -> Response:
    """Execute edge pipeline flow: decoy check -> upstream proxy -> unconditional mutation."""
    # 1. Decoy / trap handling (only if runtime configured)
    is_trap = False
    try:
        is_trap = is_trap_path(ctx.path)
    except Exception as trap_cfg_err:
        logger.warning("Trap config/predicate fault for %s: %s; falling through to upstream", ctx.path, trap_cfg_err)
        _append_fault_record({
            "event_type": "trap_config_error",
            "path": ctx.path,
            "error": str(trap_cfg_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    if is_trap:
        try:
            handle_decoy_fn, _ = _get_offense_hooks()
            if handle_decoy_fn is not None:
                decoy_resp = handle_decoy_fn(ctx, session)
                if decoy_resp is not None:
                    session.state = "SANDBOX"
                    session.decision = "SANDBOX"
                    if ctx.path not in session.traps_triggered:
                        session.traps_triggered.append(ctx.path)
                    try:
                        log_event(ctx, session, "OFFENSE", "SANDBOX", decoy_resp.status_code, ["TRAP_DECOY_HIT"])
                        record_decision(session, "OFFENSE", "SANDBOX")
                    except Exception as log_err:
                        logger.error("Failed to log decoy event: %s", log_err)
                    try:
                        save_session(session)
                    except Exception as exc:
                        logger.error("Failed to save session after decoy hit: %s", exc)
                    return decoy_resp
        except Exception as decoy_err:
            logger.error("Decoy handling fault for %s: %s; falling through to upstream", ctx.path, decoy_err)
            _append_fault_record({
                "event_type": "decoy_handling_fault",
                "session_id": getattr(session, "session_id", "unknown"),
                "path": ctx.path,
                "error": str(decoy_err),
                "ts": datetime.now(timezone.utc).isoformat(),
            })

    # 2. Upstream fetch (tracked; forward once, never replay possibly sent non-idempotent request)
    upstream_attempted: bool = True
    upstream_sent: bool = False
    upstream_captured: httpx.Response | None = None

    try:
        upstream = await proxy(ctx)
        upstream_sent = True
        upstream_captured = upstream
    except httpx.TimeoutException as exc:
        upstream_sent = True
        logger.error(
            "Upstream proxy request timed out for %s %s: %s",
            ctx.request.method,
            ctx.path,
            exc,
        )
        try:
            _append_fault_record({
                "event_type": "proxy_origin_timeout",
                "session_id": getattr(session, "session_id", "unknown"),
                "client_key": getattr(ctx, "client_key", ""),
                "path": ctx.path,
                "method": getattr(ctx.request, "method", "GET"),
                "status_code": 504,
                "error": str(exc),
                "upstream_attempted": upstream_attempted,
                "upstream_sent": upstream_sent,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        try:
            log_event(ctx, session, "ORIGIN", "SANDBOX", 504, ["ORIGIN_TIMEOUT"])
            record_decision(session, "ORIGIN", "SANDBOX")
        except Exception:
            pass
        return Response(
            content=b"Gateway Timeout",
            status_code=504,
            media_type="text/plain",
        )
    except Exception as exc:
        upstream_sent = True
        logger.error(
            "Upstream proxy connection failed for %s %s: %s",
            ctx.request.method,
            ctx.path,
            exc,
        )
        try:
            _append_fault_record({
                "event_type": "proxy_origin_error",
                "session_id": getattr(session, "session_id", "unknown"),
                "client_key": getattr(ctx, "client_key", ""),
                "path": ctx.path,
                "method": getattr(ctx.request, "method", "GET"),
                "status_code": 502,
                "error": str(exc),
                "upstream_attempted": upstream_attempted,
                "upstream_sent": upstream_sent,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        try:
            log_event(ctx, session, "ORIGIN", "SANDBOX", 502, ["ORIGIN_CONNECT_ERROR"])
            record_decision(session, "ORIGIN", "SANDBOX")
        except Exception:
            pass
        return Response(
            content=b"Bad Gateway: Origin unreachable",
            status_code=502,
            media_type="text/plain",
        )

    # 3. Post-upstream processing with complete internal fault guarding
    original_content = bytes(getattr(upstream_captured, "content", b""))
    original_status = int(getattr(upstream_captured, "status_code", 200))
    original_headers_raw = list(getattr(getattr(upstream_captured, "headers", None), "raw", []))

    decision = "SANDBOX"
    reasons: list[str] = []
    body = original_content
    mutated = False

    try:
        content_type = upstream_captured.headers.get("content-type", "")
        eligible = is_eligible_for_mutation(
            ctx.request.method, upstream_captured.status_code, content_type
        )
        if eligible:
            _, transform_response_fn = _get_offense_hooks()
            if transform_response_fn is not None:
                try:
                    mutated_body = transform_response_fn(ctx, session, UpstreamResponse(upstream_captured))
                    if mutated_body and mutated_body != original_content:
                        body = mutated_body
                        mutated = True
                        reasons = ["CANARY_INJECTED"]
                    else:
                        from sb.offense.injector import deterministic_fallback_core

                        body, mutated = deterministic_fallback_core(ctx, session, upstream_captured)
                        reasons = ["CANARY_INJECTED"] if mutated else ["mutation_failed_pass"]
                except Exception as mut_err:
                    logger.error(
                        "Primary offense mutation error for %s: %s; running registered deterministic fallback",
                        ctx.path,
                        mut_err,
                    )
                    _append_fault_record({
                        "event_type": "mutation_hook_error",
                        "session_id": getattr(session, "session_id", "unknown"),
                        "client_key": getattr(ctx, "client_key", ""),
                        "path": ctx.path,
                        "error": str(mut_err),
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                    from sb.offense.injector import deterministic_fallback_core

                    body, mutated = deterministic_fallback_core(ctx, session, upstream_captured)
                    reasons = ["CANARY_INJECTED"] if mutated else ["mutation_failed_pass"]
            else:
                from sb.offense.injector import deterministic_fallback_core

                body, mutated = deterministic_fallback_core(ctx, session, upstream_captured)
                reasons = ["CANARY_INJECTED"] if mutated else ["mutation_failed_pass"]
        else:
            body = original_content
            mutated = False
            reasons = ["mutation_skipped_noneligible"]
    except Exception as fallback_err:
        # TOTAL internal mutation fault: best-effort captured original upstream status/body/headers UNMUTATED
        logger.exception(
            "Total mutation internal fault for %s: %s; reverting to unmutated upstream pass",
            ctx.path,
            fallback_err,
        )
        _append_fault_record({
            "event_type": "total_mutation_fault",
            "session_id": getattr(session, "session_id", "unknown"),
            "path": ctx.path,
            "error": str(fallback_err),
            "outcome": "failed",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        body = original_content
        mutated = False
        reasons = ["mutation_internal_fault_unmutated_pass"]

    # Telemetry logging and session saving
    try:
        log_event(ctx, session, "ORIGIN", decision, upstream_captured.status_code, reasons)
        record_decision(session, "ORIGIN", decision)
        save_session(session)
    except Exception as internal_err:
        logger.exception("Internal store fault during logging/saving: %s; reverting to unmutated upstream pass", internal_err)
        _append_fault_record({
            "event_type": "internal_pipeline_fault",
            "session_id": getattr(session, "session_id", "unknown"),
            "client_key": getattr(ctx, "client_key", ""),
            "path": ctx.path,
            "error": str(internal_err),
            "outcome": "failed",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        # Fatal store fault during postfetch logging/saving: return UNMUTATED captured upstream response
        body = original_content
        mutated = False
        decision = "SANDBOX"
        reasons = ["mutation_failed_store_fault"]

    try:
        return build_proxy_response(upstream_captured, body, mutated, ctx.request.method)
    except Exception as resp_err:
        logger.exception("build_proxy_response fault: %s", resp_err)
        _append_fault_record({
            "event_type": "response_build_fault",
            "error": str(resp_err),
            "path": ctx.path,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        # Robust fallback: preserve upstream headers (filtering hop-by-hop), HEAD empty body, repeated cookies
        is_head = ctx.request.method.upper() == "HEAD"
        is_empty = original_status in (204, 205, 304)
        resp_body = b"" if (is_head or is_empty) else original_content
        fallback_resp = Response(content=resp_body, status_code=original_status)
        raw_headers = []
        for k_bytes, v_bytes in original_headers_raw:
            k_lower = k_bytes.lower().decode("latin1", errors="replace")
            if k_lower in HOP_BY_HOP_HEADERS or k_lower == "connection":
                continue
            if k_lower == "content-length" and not is_head:
                continue
            raw_headers.append((k_bytes, v_bytes))
        if not is_head and not is_empty:
            raw_headers.append((b"content-length", str(len(resp_body)).encode("ascii")))
        fallback_resp.raw_headers = raw_headers
        return fallback_resp
