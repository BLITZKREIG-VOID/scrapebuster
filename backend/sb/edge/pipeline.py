"""Edge pipeline — request decision flow for Phase0.

Pipeline: context -> session -> telemetry/decoy -> upstream-fetch -> unconditional-mutation -> response.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Request, Response

from ..config import is_trap_path
from ..store.ledger import append_event
from .context import RequestContext, build_context
from .intel import init_request, record_decision
from .proxy import HOP_BY_HOP_HEADERS, UpstreamResponse, proxy
from .session import Session, sessions
from .telemetry import TelemetryTap

logger = logging.getLogger("sb.edge.pipeline")


def extract_canary_ids(body: bytes) -> tuple[str, ...]:
    """Extract served canary token IDs from response payload bytes (PRD FR1.5)."""
    if not body:
        return ()
    try:
        from ..hooks import extract_canary_ids as hook_extract

        if callable(hook_extract):
            res = hook_extract(body)
            if res:
                return tuple(res)
    except Exception:
        pass

    try:
        from ..offense.injector import extract_canary_ids as inj_extract

        if callable(inj_extract):
            res = inj_extract(body)
            if res:
                return tuple(res)
    except Exception:
        pass

    # Standard fallback regex matching SB-CANARY-<session_hash>-<seq>
    pattern = re.compile(rb"SB-CANARY-[a-fA-F0-9]+-\d+")
    matches = pattern.findall(body)
    if not matches:
        return ()
    found = [m.decode("ascii", errors="replace") for m in matches]
    return tuple(dict.fromkeys(found))

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
    """Log event hook for parameter validation, forensic recording, and test fault injection."""
    if reasons is None:
        reasons = []

    actual_stage = stage or layer or "ORIGIN"

    if actual_stage not in TRAFFIC_STAGES and actual_stage not in TRAFFIC_LAYERS:
        raise ValueError(f"Unsupported traffic stage/layer: {actual_stage}")
    if decision not in TRAFFIC_DECISIONS:
        raise ValueError(f"Unsupported traffic decision: {decision}")

    event_id = f"evt-{uuid.uuid4().hex[:8]}"

    if session is not None and event_id not in session.event_ids:
        session.event_ids.append(event_id)
    if session is not None and reasons:
        for r in reasons:
            if r not in session.reasons:
                session.reasons.append(r)


async def handle(request: Request) -> Response:
    """Handle an incoming request through the guarded edge pipeline."""
    t_start = time.perf_counter()

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
        session.record_request(ctx)
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

    # Measure passive tap overhead (PRD FR1.1, FR1.4 tap added latency target p95 < 5ms)
    tap_latency_ms = (time.perf_counter() - t_start) * 1000.0

    try:
        response = await _handle_request(ctx, session, tap_latency_ms=tap_latency_ms)
        return response
    except Exception as unhandled_err:
        logger.exception("Unhandled pipeline error: %s", unhandled_err)
        _append_fault_record({
            "event_type": "unhandled_pipeline_error",
            "path": getattr(ctx, "path", "/"),
            "error": str(unhandled_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        return Response(content=b"Bad Gateway", status_code=502, media_type="text/plain")


async def _handle_request(ctx: RequestContext, session: Session, tap_latency_ms: float = 0.0) -> Response:
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
                    # Invoke log_event hook (allows tests to monkeypatch and inject storage/audit faults)
                    log_event(
                        ctx,
                        session,
                        stage="OFFENSE",
                        decision="SANDBOX",
                        status_code=decoy_resp.status_code,
                        reasons=["TRAP_DECOY_HIT"],
                    )
                    session.state = "SANDBOX"
                    session.decision = "SANDBOX"
                    session.add_trap_triggered(ctx.path)
                    record_decision(session, "OFFENSE", "SANDBOX")
                    served_canaries = extract_canary_ids(getattr(decoy_resp, "body", b""))
                    for cid in served_canaries:
                        session.add_canary_exposed(cid)
                    t_enq_start = time.perf_counter()
                    try:
                        TelemetryTap.enqueue_request(
                            ctx,
                            session,
                            response_status=decoy_resp.status_code,
                            stage="OFFENSE",
                            decision="SANDBOX",
                            reasons=["TRAP_DECOY_HIT"],
                            served_canary_ids=served_canaries,
                            tap_latency_ms=tap_latency_ms + (time.perf_counter() - t_enq_start) * 1000.0,
                        )
                    except Exception as storage_err:
                        logger.error("Decoy telemetry enqueue fault for %s: %s", ctx.path, storage_err)
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
            record_decision(session, "ORIGIN", "SANDBOX")
            TelemetryTap.enqueue_request(
                ctx,
                session,
                response_status=504,
                stage="ORIGIN",
                decision="SANDBOX",
                reasons=["ORIGIN_TIMEOUT"],
                tap_latency_ms=tap_latency_ms,
            )
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
            record_decision(session, "ORIGIN", "SANDBOX")
            TelemetryTap.enqueue_request(
                ctx,
                session,
                response_status=502,
                stage="ORIGIN",
                decision="SANDBOX",
                reasons=["ORIGIN_CONNECT_ERROR"],
                tap_latency_ms=tap_latency_ms,
            )
        except Exception:
            pass
        return Response(
            content=b"Bad Gateway: Origin unreachable",
            status_code=502,
            media_type="text/plain",
        )

    # 3. Post-upstream processing with Dynamic Router and complete internal fault guarding
    original_content = bytes(getattr(upstream_captured, "content", b""))
    original_status = int(getattr(upstream_captured, "status_code", 200))
    original_headers_raw = list(getattr(getattr(upstream_captured, "headers", None), "raw", []))

    decision = "SANDBOX"
    reasons: list[str] = []
    body = original_content
    mutated = False
    route_class = "unknown"

    try:
        from ..router.router import router as dynamic_router

        router_res = dynamic_router.evaluate(ctx, session)
        decision = router_res.decision
        route_class = router_res.route_class
        router_decision = getattr(router_res, "router_decision", decision) or decision
        session.decision = decision
        session.state = router_res.state
        session.trust_score = router_res.trust_score
        session.ar_classifier_decision = getattr(router_res, "ar_classifier_decision", None) or decision
        session.confidence_score = router_res.confidence_score
        session.router_decision = router_decision
        reasons = list(router_res.reasons)
    except Exception as router_err:
        logger.error("Router evaluation error for %s: %s; fail-offensive to SANDBOX", ctx.path, router_err)
        _append_fault_record({
            "event_type": "router_evaluation_fault",
            "session_id": getattr(session, "session_id", "unknown"),
            "path": ctx.path,
            "error": str(router_err),
            "fallback_decision": "SANDBOX",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        decision = "SANDBOX"
        router_decision = "SANDBOX"
        session.decision = "SANDBOX"
        session.state = "SANDBOX"
        reasons = ["ROUTER_FAULT_FAIL_OFFENSIVE"]
        route_class = "router_fault_fallback"

    try:
        if decision == "FAST_PATH":
            # FR-2.3 Fast Path bypass to origin with ZERO response mutation
            body = original_content
            mutated = False
            if "FAST_PATH_BYPASS" not in reasons:
                reasons.append("FAST_PATH_BYPASS")
        else:
            content_type = upstream_captured.headers.get("content-type", "")
            eligible = is_eligible_for_mutation(
                ctx.request.method, upstream_captured.status_code, content_type
            )
            if eligible:
                _, transform_response_fn = _get_offense_hooks()
                canary_reason = "ADAPTIVE_GRADUATED_CANARY" if router_decision == "ADAPTIVE" else "CANARY_INJECTED"
                if transform_response_fn is not None:
                    try:
                        mutated_body = transform_response_fn(ctx, session, UpstreamResponse(upstream_captured))
                        if mutated_body and mutated_body != original_content:
                            body = mutated_body
                            mutated = True
                            reasons = [canary_reason]
                        else:
                            from sb.offense.injector import deterministic_fallback_core

                            body, mutated = deterministic_fallback_core(ctx, session, upstream_captured)
                            reasons = [canary_reason] if mutated else ["mutation_failed_pass"]
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

        # Invoke log_event hook inside the mutation try block (allows tests to monkeypatch and trigger fallback)
        log_event(
            ctx,
            session,
            stage="ORIGIN",
            decision=decision,
            status_code=upstream_captured.status_code,
            reasons=reasons,
        )
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

    # Telemetry logging off-request path via TelemetryTap (PRD FR1.1, FR1.4)
    served_canaries = extract_canary_ids(body)
    for cid in served_canaries:
        session.add_canary_exposed(cid)
    t_enq_start = time.perf_counter()
    try:
        record_decision(session, "ORIGIN", decision)
        TelemetryTap.enqueue_request(
            ctx,
            session,
            response_status=upstream_captured.status_code,
            stage="ORIGIN",
            decision=decision,
            reasons=reasons,
            served_canary_ids=served_canaries,
            tap_latency_ms=tap_latency_ms + (time.perf_counter() - t_enq_start) * 1000.0,
            route_class=route_class,
        )
    except Exception as internal_err:
        logger.exception("Internal telemetry tap enqueue fault: %s", internal_err)
        _append_fault_record({
            "event_type": "telemetry_enqueue_fault",
            "session_id": getattr(session, "session_id", "unknown"),
            "client_key": getattr(ctx, "client_key", ""),
            "path": ctx.path,
            "error": str(internal_err),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

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
