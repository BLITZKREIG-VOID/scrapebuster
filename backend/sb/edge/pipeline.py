import json
import uuid
from datetime import datetime, timezone

from fastapi import Request, Response

from ..hooks import trap_hooks
from ..store.db import get_connection
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
                ctx.header_fp, layer, decision, session.l1_score,
                json.dumps(reasons),
            ),
        )
        conn.commit()
    finally:
        conn.close()


async def handle(request: Request) -> Response:
    ctx = build_context(request)
    session = sessions.get_or_create(ctx)

    from .intel import init_request, record_decision
    init_request(ctx, session)

    # ── Layer 1 ─────────────────────────────────────────────────────────────
    l1: L1Result = l1_run(ctx)
    session.l1_score = l1.score
    for r in l1.reasons:
        if r not in session.l1_reasons:
            session.l1_reasons.append(r)

    if l1.decision == "BLOCK":
        log_event(ctx, session, "L1", "BLOCK", 403, l1.reasons)
        record_decision(session, "L1", "BLOCK")
        return Response(content=b"Forbidden", status_code=403)

    if l1.decision == "CHALLENGE":
        if session.state == "VERIFIED":
            # Pass through
            log_event(ctx, session, "L1", "CHALLENGE_BYPASSED", 0, l1.reasons)
            record_decision(session, "L1", "CHALLENGE_BYPASSED")
        else:
            log_event(ctx, session, "L1", "CHALLENGE", 403, l1.reasons)
            session.state = "CHALLENGED"
            record_decision(session, "L1", "CHALLENGE")
            from .layer2 import generate_challenge_response
            return generate_challenge_response(session)

    elif l1.decision == "ESCALATE":
        log_event(ctx, session, "L1", "ESCALATE", 0, l1.reasons)
        session.state = "SUSPICIOUS"
        record_decision(session, "L1", "ESCALATE")
    else:
        record_decision(session, "L1", "ALLOW")

    # ── TrapHooks (Layer 3 — INT-08) ────────────────────────────────────────
    trap = trap_hooks.classify_request(ctx, session)
    if trap:
        session.mark_trapped(trap)
        if trap.trap_id not in session.traps_triggered:
            session.traps_triggered.append(trap.trap_id)
        record_decision(session, "L3", "TRAP")
        resp = trap_hooks.handle_decoy(ctx, session)
        if resp:
            return resp

    # ── Proxy to origin ─────────────────────────────────────────────────────
    upstream = await proxy(ctx)
    body = trap_hooks.transform_response(ctx, session, UpstreamResponse(upstream))

    # Log the final outcome (ALLOW or carry-through after CHALLENGE/ESCALATE)
    final_decision = l1.decision if l1.decision in ("ALLOW", "ESCALATE", "CHALLENGE") else "ALLOW"
    log_event(ctx, session, "L1", final_decision, upstream.status_code, l1.reasons)
    record_decision(session, "ORIGIN", final_decision)

    out_headers = dict(upstream.headers)
    out_headers.pop("content-length", None)
    out_headers.pop("transfer-encoding", None)
    out_headers.pop("content-encoding", None)

    return Response(content=body, status_code=upstream.status_code, headers=out_headers)
