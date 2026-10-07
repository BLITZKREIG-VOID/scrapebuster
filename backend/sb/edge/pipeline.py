"""Edge pipeline — request decision flow for Phase0.

Pipeline: context -> session -> telemetry/decoy -> upstream-fetch -> unconditional-mutation -> response.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Request, Response

from ..config import SB_TRAP_API_PATH, SB_TRAP_PATHS
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


def is_trap_path(path: str) -> bool:
    """Check if the path matches runtime-configured trap paths.

    No hard-coded decoy routes; returns False if not configured.
    """
    if not SB_TRAP_PATHS and not SB_TRAP_API_PATH:
        return False
    norm_path = path.rstrip("/") if path != "/" else "/"
    trap_paths = [p.rstrip("/") if p != "/" else "/" for p in SB_TRAP_PATHS]
    if norm_path in trap_paths:
        return True
    if SB_TRAP_API_PATH:
        api_norm = SB_TRAP_API_PATH.rstrip("/") if SB_TRAP_API_PATH != "/" else "/"
        if norm_path == api_norm:
            return True
    return False


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
    preserves upstream HEAD Content-Length, and updates Content-Length
    for mutated bodies.
    """
    status_code = upstream.status_code
    resp_body = b"" if method.upper() == "HEAD" else body

    resp = Response(content=resp_body, status_code=status_code)

    # Connection-nominated headers to strip
    connection_tokens = set()
    conn_hdr = upstream.headers.get("connection", "")
    if conn_hdr:
        for token in conn_hdr.split(","):
            t = token.strip().lower()
            if t:
                connection_tokens.add(t)

    drop_headers = HOP_BY_HOP_HEADERS | connection_tokens | {"content-encoding"}

    raw_headers: list[tuple[bytes, bytes]] = []
    content_length_added = False

    # Upstream raw headers preserves exact duplicates including repeated Set-Cookie
    for k_bytes, v_bytes in upstream.headers.raw:
        k_lower = k_bytes.lower().decode("latin1", errors="replace")
        if k_lower in drop_headers:
            continue
        if k_lower == "content-length":
            if method.upper() == "HEAD":
                # Preserve upstream HEAD Content-Length exactly
                raw_headers.append((k_bytes, v_bytes))
                content_length_added = True
            elif not mutated:
                # Unmutated body keeps upstream content-length
                raw_headers.append((k_bytes, v_bytes))
                content_length_added = True
            continue
        raw_headers.append((k_bytes, v_bytes))

    # Recompute or add Content-Length for non-HEAD responses with bodies
    if method.upper() != "HEAD" and status_code not in (204, 205, 304):
        if mutated or not content_length_added:
            raw_headers.append((b"content-length", str(len(resp_body)).encode("ascii")))

    resp.raw_headers = raw_headers
    return resp


def log_event(
    ctx: RequestContext,
    session: Session,
    layer: str,
    decision: str,
    status_code: int,
    reasons: list[str] | None = None,
    risk_score: int | None = None,
) -> None:
    """Log a traffic event to database and append to forensic ledger."""
    if reasons is None:
        reasons = []
    if layer not in TRAFFIC_STAGES and layer not in TRAFFIC_LAYERS:
        raise ValueError(f"Unsupported traffic stage/layer: {layer}")
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

    session_id = session.session_id if session else "unknown"
    client_key = ctx.client_key if ctx else ""
    ip = ctx.ip if ctx else "127.0.0.1"
    method = ctx.request.method if ctx and ctx.request else "GET"
    path = ctx.path if ctx else "/"
    user_agent = ctx.user_agent if ctx else ""
    header_fp = ctx.header_fp if ctx else ""

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
                layer,
                layer,
                decision,
                0 if risk_score is None else risk_score,
                json.dumps(reasons),
            ),
        )
        conn.commit()
    except Exception as db_err:
        logger.error("Failed to insert traffic_event: %s", db_err)
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
        "stage": layer,
        "layer": layer,
        "decision": decision,
        "risk_score": 0 if risk_score is None else risk_score,
        "reasons": reasons,
        "ts": ts,
    }
    try:
        append_event("traffic", record)
    except Exception as ledger_err:
        logger.error("Failed to append traffic event to ledger: %s", ledger_err)


async def handle(request: Request) -> Response:
    """Handle an incoming request through the edge pipeline."""
    ctx = build_context(request)
    session = sessions.get_or_create(ctx)

    try:
        init_request(ctx, session)
        try:
            save_session(session)
        except Exception as sess_err:
            logger.error("Failed to save session before fetch: %s", sess_err)
            _append_fault_record({
                "event_type": "pre_fetch_session_save_error",
                "session_id": session.session_id,
                "client_key": ctx.client_key,
                "path": ctx.path,
                "error": str(sess_err),
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        return await _handle_request(ctx, session)
    finally:
        try:
            save_session(session)
        except Exception as sess_err:
            logger.error("Failed to save session in finally: %s", sess_err)
            _append_fault_record({
                "event_type": "post_fetch_session_save_error",
                "session_id": session.session_id,
                "client_key": ctx.client_key,
                "path": ctx.path,
                "error": str(sess_err),
                "ts": datetime.now(timezone.utc).isoformat(),
            })


async def _handle_request(ctx: RequestContext, session: Session) -> Response:
    """Execute edge pipeline flow: decoy check -> upstream proxy -> unconditional mutation."""
    # 1. Decoy / trap handling (only if runtime configured)
    if is_trap_path(ctx.path):
        handle_decoy_fn, _ = _get_offense_hooks()
        if handle_decoy_fn is not None:
            decoy_resp = handle_decoy_fn(ctx, session)
            if decoy_resp is not None:
                session.state = "SANDBOX"
                session.decision = "SANDBOX"
                if ctx.path not in session.traps_triggered:
                    session.traps_triggered.append(ctx.path)
                log_event(ctx, session, "OFFENSE", "SANDBOX", decoy_resp.status_code, ["TRAP_DECOY_HIT"])
                record_decision(session, "OFFENSE", "SANDBOX")
                try:
                    save_session(session)
                except Exception as exc:
                    logger.error("Failed to save session after decoy hit: %s", exc)
                return decoy_resp

    # 2. Upstream fetch (exactly once, never retry non-idempotent)
    try:
        upstream = await proxy(ctx)
    except httpx.TimeoutException as exc:
        logger.error(
            "Upstream proxy request timed out for %s %s: %s",
            ctx.request.method,
            ctx.path,
            exc,
        )
        _append_fault_record({
            "event_type": "proxy_origin_timeout",
            "session_id": session.session_id,
            "client_key": ctx.client_key,
            "path": ctx.path,
            "method": ctx.request.method,
            "status_code": 504,
            "error": str(exc),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        log_event(ctx, session, "ORIGIN", "SANDBOX", 504, ["ORIGIN_TIMEOUT"])
        record_decision(session, "ORIGIN", "SANDBOX")
        return Response(
            content=b"Gateway Timeout",
            status_code=504,
            media_type="text/plain",
        )
    except Exception as exc:
        logger.error(
            "Upstream proxy connection failed for %s %s: %s",
            ctx.request.method,
            ctx.path,
            exc,
        )
        _append_fault_record({
            "event_type": "proxy_origin_error",
            "session_id": session.session_id,
            "client_key": ctx.client_key,
            "path": ctx.path,
            "method": ctx.request.method,
            "status_code": 502,
            "error": str(exc),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        log_event(ctx, session, "ORIGIN", "SANDBOX", 502, ["ORIGIN_CONNECT_ERROR"])
        record_decision(session, "ORIGIN", "SANDBOX")
        return Response(
            content=b"Bad Gateway: Origin unreachable",
            status_code=502,
            media_type="text/plain",
        )

    # 3. Post-upstream processing with fault resilience
    # Decision is SANDBOX for all protected Phase 0 origin traffic
    decision = "SANDBOX"
    reasons: list[str] = []

    content_type = upstream.headers.get("content-type", "")
    eligible = is_eligible_for_mutation(
        ctx.request.method, upstream.status_code, content_type
    )

    body = upstream.content
    mutated = False

    if eligible:
        _, transform_response_fn = _get_offense_hooks()
        if transform_response_fn is not None:
            try:
                mutated_body = transform_response_fn(ctx, session, UpstreamResponse(upstream))
                if mutated_body and mutated_body != upstream.content:
                    body = mutated_body
                    mutated = True
                    reasons = ["CANARY_INJECTED"]
                else:
                    # Identity bytes or empty: run shared deterministic fallback helper
                    from sb.offense.injector import deterministic_fallback_core

                    body, mutated = deterministic_fallback_core(ctx, session, upstream)
                    reasons = ["CANARY_INJECTED"] if mutated else ["mutation_failed_pass"]
            except Exception as mut_err:
                logger.error(
                    "Offense mutation failed for %s: %s; using deterministic fallback helper",
                    ctx.path,
                    mut_err,
                )
                _append_fault_record({
                    "event_type": "mutation_hook_error",
                    "session_id": session.session_id,
                    "client_key": ctx.client_key,
                    "path": ctx.path,
                    "error": str(mut_err),
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
                from sb.offense.injector import deterministic_fallback_core

                body, mutated = deterministic_fallback_core(ctx, session, upstream)
                reasons = ["CANARY_INJECTED"] if mutated else ["mutation_failed_pass"]
        else:
            from sb.offense.injector import deterministic_fallback_core

            body, mutated = deterministic_fallback_core(ctx, session, upstream)
            reasons = ["CANARY_INJECTED"] if mutated else ["mutation_failed_pass"]
    else:
        # Non-eligible content (HEAD, 204, binary, etc.) remains unmutated
        body = upstream.content
        mutated = False
        reasons = ["mutation_skipped_noneligible"]

    try:
        log_event(ctx, session, "ORIGIN", decision, upstream.status_code, reasons)
        record_decision(session, "ORIGIN", decision)
        save_session(session)
    except Exception as internal_err:
        logger.exception("Internal store fault during logging: %s; passing upstream response", internal_err)
        _append_fault_record({
            "event_type": "internal_pipeline_fault",
            "session_id": session.session_id,
            "client_key": ctx.client_key,
            "path": ctx.path,
            "error": str(internal_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    return build_proxy_response(upstream, body, mutated, ctx.request.method)
