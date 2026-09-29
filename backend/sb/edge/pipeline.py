"""
Edge pipeline — §3 request decision flow.

Order (exact per §3):
  1. blocked-session check
  2. Layer 1
  3. THROTTLE / BLOCK short-circuit
  4. TrapHooks classify (L3)
  5. RESTRICTED session check
  6. clearance validation → L2 interstitial if not cleared
  7. proxy + response transformation
"""

import json
import uuid
from datetime import datetime, timezone
from collections.abc import Callable

from fastapi import Request, Response

from ..hooks import trap_hooks
from ..store.db import get_connection
from ..store.sessions import save_session
from .context import RequestContext, build_context
from .layer1 import L1Result
from .layer1 import run as l1_run
from .proxy import UpstreamResponse, proxy
from .session import Session, sessions

EXEMPT = ["/health", "/favicon.ico"]


def is_exempt(ctx: RequestContext) -> bool:
    return (
        ctx.path in EXEMPT
        or ctx.path.startswith("/api/")
        or ctx.path.startswith("/_sb/")
        or ctx.path.startswith("/static/")
    )


def log_event(
    ctx: RequestContext,
    session: Session,
    layer: str,
    decision: str,
    status_code: int,
    reasons: list | None = None,
    risk_score: int | None = None,
) -> None:
    if reasons is None:
        reasons = []

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
                event_id, ts, session.session_id, ctx.client_key, ctx.ip,
                ctx.request.method, ctx.path, status_code, ctx.user_agent,
                ctx.header_fp, layer, decision,
                session.l1_score if risk_score is None else risk_score,
                json.dumps(reasons),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def clearance_valid(ctx: RequestContext, session: Session) -> bool:
    """
    Return True if this request carries a valid sb_clear HMAC cookie
    bound to this client_key, meaning the session passed L2 previously.
    A valid clearance also sets session.state = VERIFIED for downstream checks.
    """
    from ..edge.layer2 import validate_clearance

    cookie = ctx.request.cookies.get("sb_clear", "")
    if validate_clearance(cookie, ctx.client_key):
        session.state = "VERIFIED"
        return True
    return False


async def handle(request: Request) -> Response:
    ctx = build_context(request)
    session = sessions.get_or_create(ctx)

    from .intel import init_request, record_decision
    try:
        init_request(ctx, session)
        return await _handle_request(ctx, session, record_decision)
    finally:
        save_session(session)


async def _handle_request(
    ctx: RequestContext,
    session: Session,
    record_decision: Callable[[Session, str, str], None],
) -> Response:
    # ── 1. Blocked-session short-circuit ────────────────────────────────────
    if session.state == "BLOCKED" and not session.block_expired():
        log_event(ctx, session, "L1", "BLOCK", 403, session.l1_reasons)
        record_decision(session, "L1", "BLOCK")
        return Response(content=b"Forbidden", status_code=403)
    if session.state == "BLOCKED":
        session.state = "NEW"
        session.block_until = ""

    # ── 2. Layer 1 ───────────────────────────────────────────────────────────
    l1: L1Result = l1_run(ctx, session)
    session.l1_score = l1.score
    for r in l1.reasons:
        if r not in session.l1_reasons:
            session.l1_reasons.append(r)

    if l1.decision == "BLOCK":
        session.state = "BLOCKED"
        if l1.block_until:
            session.block_until = l1.block_until
        log_event(ctx, session, "L1", "BLOCK", 403, l1.reasons)
        record_decision(session, "L1", "BLOCK")
        return Response(content=b"Forbidden", status_code=403)

    if l1.decision == "THROTTLE":
        session.state = "THROTTLED"
        log_event(ctx, session, "L1", "THROTTLE", 429, l1.reasons)
        record_decision(session, "L1", "THROTTLE")
        return Response(
            content=b"Too Many Requests",
            status_code=429,
            headers={"Retry-After": "10"},
        )

    # ── 3. TrapHooks classify (L3) — must come before RESTRICTED check ───────
    trap = trap_hooks.classify_request(ctx, session)
    if trap:
        session.mark_trapped(trap)
        if trap.trap_id not in session.traps_triggered:
            session.traps_triggered.append(trap.trap_id)
        record_decision(session, "L3", "TRAP")
        resp = trap_hooks.handle_decoy(ctx, session)
        if resp:
            log_event(ctx, session, "L3", "TRAP", resp.status_code, l1.reasons)
            return resp

    # ── 4. RESTRICTED session ─────────────────────────────────────────────────
    if session.state == "RESTRICTED":
        log_event(ctx, session, "L2", "RESTRICT", 403, [])
        record_decision(session, "L2", "RESTRICT")
        body = (
            b"<!DOCTYPE html><html><head><title>Access Restricted</title></head>"
            b"<body><h1>403 Restricted</h1>"
            b"<p>Your access has been restricted.</p></body></html>"
        )
        return Response(content=body, media_type="text/html", status_code=403)

    # ── 5. Layer 2 interstitial / clearance check ────────────────────────────
    # Applies to ESCALATE decisions on document requests.
    # Trapped sessions bypass the interstitial — they already proved something.
    needs_interstitial = (
        l1.decision == "ESCALATE"
        and ctx.is_document
        and session.state != "TRAPPED"
        and not clearance_valid(ctx, session)
    )

    if needs_interstitial:
        from .layer2 import generate_interstitial
        session.state = "ESCALATED"
        log_event(ctx, session, "L1", "ESCALATE", 200, l1.reasons)
        record_decision(session, "L1", "ESCALATE")
        log_event(ctx, session, "L2", "CHALLENGE", 200, [], risk_score=0)
        record_decision(session, "L2", "CHALLENGE")
        return generate_interstitial(session)

    # Non-ESCALATE ALLOW path: record and continue
    if l1.decision == "ALLOW":
        record_decision(session, "L1", "ALLOW")
    elif l1.decision == "ESCALATE" and not needs_interstitial:
        # Clearance was already established. Record the decision once; the
        # terminal event below carries the actual upstream status code.
        record_decision(session, "L1", "ESCALATE")

    # ── 6. Proxy + response transformation ──────────────────────────────────
    upstream = await proxy(ctx)
    body = trap_hooks.transform_response(ctx, session, UpstreamResponse(upstream))

    final_decision = "TRAP" if session.state == "TRAPPED" else l1.decision
    log_event(ctx, session, "L3" if session.state == "TRAPPED" else "L1",
              final_decision, upstream.status_code, l1.reasons)
    record_decision(session, "ORIGIN", final_decision)

    out_headers = dict(upstream.headers)
    out_headers.pop("content-length", None)
    out_headers.pop("transfer-encoding", None)
    out_headers.pop("content-encoding", None)

    return Response(content=body, status_code=upstream.status_code, headers=out_headers)
