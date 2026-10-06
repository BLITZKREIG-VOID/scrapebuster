"""Edge pipeline — request decision flow for Phase0.

Pipeline: context -> session -> telemetry/decoy -> upstream-fetch -> unconditional-mutation -> response.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request, Response

from ..config import SB_MUTATION_MODE, SB_TRAP_API_PATH, SB_TRAP_PATHS
from ..store.db import get_connection
from ..store.sessions import save_session
from .context import RequestContext, build_context
from .intel import init_request, record_decision
from .proxy import UpstreamResponse, proxy
from .session import Session, sessions

logger = logging.getLogger("sb.edge.pipeline")

TRAFFIC_LAYERS = frozenset({"L1", "L2", "L3", "ORIGIN"})
TRAFFIC_DECISIONS = frozenset({
    "ALLOW",
    "ESCALATE",
    "CHALLENGE",
    "PASS",
    "RESTRICT",
    "THROTTLE",
    "BLOCK",
    "TRAP",
    "SANDBOX",
})


def _get_offense_hooks():
    """Resolve offense hooks provided by W2 or legacy trap fallback."""
    try:
        from sb.offense.injector import handle_decoy, transform_response

        return handle_decoy, transform_response
    except ImportError:
        pass
    try:
        from sb.trap.injector import handle_decoy, transform_response

        return handle_decoy, transform_response
    except ImportError:
        pass
    return None, None


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


def is_control_endpoint(path: str) -> bool:
    """Check if endpoint is a control health or API route that bypasses mutation."""
    return (
        path == "/health"
        or path.startswith("/api/")
        or path.startswith("/static/")
        or path == "/favicon.ico"
    )


def is_eligible_for_mutation(method: str, status_code: int, content_type: str) -> bool:
    """Return True if response is eligible for sandboxed offensive mutation."""
    if method in {"HEAD", "OPTIONS"}:
        return False
    if status_code in {204, 205, 304}:
        return False
    ct = content_type.lower()
    return "text/html" in ct or "application/json" in ct


def _deterministic_offensive_fallback(
    ctx: RequestContext,
    session: Session,
    upstream: UpstreamResponse | Any,
) -> bytes:
    """Deterministic offensive fallback when mutation hook raises or is unavailable."""
    content_bytes = getattr(upstream, "content", b"") or b""
    content_type = ""
    headers = getattr(upstream, "headers", {}) or {}
    if hasattr(headers, "get"):
        content_type = (headers.get("content-type", "") or "").lower()

    if "text/html" in content_type:
        text = content_bytes.decode("utf-8", errors="replace")
        fallback_tag = '<a href="/trap" style="display:none" aria-hidden="true" rel="nofollow"></a>'
        if fallback_tag not in text:
            lower_text = text.lower()
            body_idx = lower_text.find("<body")
            if body_idx != -1:
                close_idx = text.find(">", body_idx)
                if close_idx != -1:
                    text = text[: close_idx + 1] + fallback_tag + text[close_idx + 1 :]
                else:
                    text = text + fallback_tag
            else:
                text = text + fallback_tag
        return text.encode("utf-8")

    if "application/json" in content_type:
        try:
            data = json.loads(content_bytes.decode("utf-8"))
            if isinstance(data, dict) and "_trap" not in data:
                data["_trap"] = "offense_active"
                return json.dumps(data).encode("utf-8")
        except Exception:
            pass

    return content_bytes


def log_event(
    ctx: RequestContext,
    session: Session,
    layer: str,
    decision: str,
    status_code: int,
    reasons: list | None = None,
    risk_score: int | None = None,
) -> None:
    """Log a traffic event to the database."""
    if reasons is None:
        reasons = []
    if layer not in TRAFFIC_LAYERS:
        raise ValueError(f"Unsupported traffic layer: {layer}")
    if decision not in TRAFFIC_DECISIONS:
        raise ValueError(f"Unsupported traffic decision: {decision}")

    conn = get_connection()
    try:
        ts = datetime.now(timezone.utc).isoformat()
        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO traffic_events
               (event_id, ts, session_id, client_key, ip, method, path, status_code,
                user_agent, header_fp, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                ts,
                session.session_id,
                ctx.client_key,
                ctx.ip,
                ctx.request.method,
                ctx.path,
                status_code,
                ctx.user_agent,
                ctx.header_fp,
                layer,
                decision,
                0 if risk_score is None else risk_score,
                json.dumps(reasons),
            ),
        )
        conn.commit()
    finally:
        conn.close()


async def handle(request: Request) -> Response:
    """Handle an incoming request through the edge pipeline."""
    ctx = build_context(request)
    session = sessions.get_or_create(ctx)

    try:
        init_request(ctx, session)
        save_session(session)
        return await _handle_request(ctx, session)
    finally:
        save_session(session)


async def _handle_request(ctx: RequestContext, session: Session) -> Response:
    """Execute edge pipeline flow: decoy check -> upstream proxy -> unconditional mutation."""
    # 1. Decoy / trap handling (only if runtime configured)
    if is_trap_path(ctx.path):
        handle_decoy_fn, _ = _get_offense_hooks()
        if handle_decoy_fn is not None:
            decoy_resp = handle_decoy_fn(ctx, session)
            if decoy_resp is not None:
                session.state = "TRAPPED"
                if ctx.path not in session.traps_triggered:
                    session.traps_triggered.append(ctx.path)
                log_event(ctx, session, "L3", "TRAP", decoy_resp.status_code, ["TRAP_DECOY_HIT"])
                record_decision(session, "L3", "TRAP")
                save_session(session)
                return decoy_resp

    # 2. Upstream fetch
    try:
        upstream = await proxy(ctx)
    except Exception as exc:
        logger.error(
            "Upstream proxy request failed for %s %s: %s",
            ctx.request.method,
            ctx.path,
            exc,
        )
        # Origin outage cannot be fabricated as successful pass-through
        return Response(
            content=b"Bad Gateway: Origin unreachable",
            status_code=502,
            media_type="text/plain",
        )

    # 3. Post-upstream processing with fault resilience
    try:
        content_type = upstream.headers.get("content-type", "")
        eligible = is_eligible_for_mutation(
            ctx.request.method, upstream.status_code, content_type
        )
        control = is_control_endpoint(ctx.path)

        if eligible and not control and SB_MUTATION_MODE != "passthrough":
            _, transform_response_fn = _get_offense_hooks()
            if transform_response_fn is not None:
                try:
                    body = transform_response_fn(ctx, session, UpstreamResponse(upstream))
                except Exception as mut_err:
                    logger.error(
                        "Offense mutation failed for %s: %s; using deterministic offensive fallback",
                        ctx.path,
                        mut_err,
                    )
                    body = _deterministic_offensive_fallback(ctx, session, upstream)
            else:
                body = _deterministic_offensive_fallback(ctx, session, upstream)
            decision = "TRAP" if session.state == "TRAPPED" else "SANDBOX"
        else:
            body = upstream.content
            decision = "ALLOW"

        log_event(ctx, session, "ORIGIN", decision, upstream.status_code, [])
        record_decision(session, "ORIGIN", decision)
        save_session(session)

        out_headers = dict(upstream.headers)
        out_headers.pop("content-length", None)
        out_headers.pop("transfer-encoding", None)
        out_headers.pop("content-encoding", None)

        return Response(
            content=body,
            status_code=upstream.status_code,
            headers=out_headers,
        )
    except Exception as pipeline_err:
        logger.exception(
            "Internal proxy pipeline fault on %s: %s; returning captured upstream bytes",
            ctx.path,
            pipeline_err,
        )
        # Internal proxy pipeline faults return captured upstream bytes unmutated with loud logs
        fallback_headers = dict(upstream.headers)
        fallback_headers.pop("content-length", None)
        fallback_headers.pop("transfer-encoding", None)
        fallback_headers.pop("content-encoding", None)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=fallback_headers,
        )
