import json
import uuid
from datetime import datetime, timezone

from fastapi import Request, Response

from ..hooks import trap_hooks
from ..store.db import get_connection
from .context import RequestContext, build_context
from .proxy import UpstreamResponse, proxy
from .session import Session, sessions

EXEMPT = ["/health", "/favicon.ico"]

def is_exempt(ctx: RequestContext) -> bool:
    return ctx.path in EXEMPT or ctx.path.startswith("/api/") or ctx.path.startswith("/_sb/") or ctx.path.startswith("/static/")

def log_event(ctx: RequestContext, session: Session, layer: str, decision: str, status_code: int, reasons: list | None = None):
    if reasons is None:
        reasons = []
        
    conn = get_connection()
    try:
        ts = datetime.now(timezone.utc).isoformat()
        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO traffic_events 
               (event_id, ts, session_id, client_key, ip, method, path, status_code, user_agent, header_fp, layer, decision, risk_score, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, ts, session.session_id, ctx.client_key, ctx.ip, ctx.request.method, ctx.path,
                status_code, ctx.user_agent, ctx.header_fp, layer, decision, session.l1_score, json.dumps(reasons)
            )
        )
        conn.commit()
    finally:
        conn.close()

async def handle(request: Request) -> Response:
    ctx = build_context(request)
    
    # In a fully fleshed out version, exempt routes return normally (or handled entirely by main.py)
    # The pipeline only handles the catch-all
    
    session = sessions.get_or_create(ctx)
    
    # --- INT-04 Stub: Layer 1 returns ALLOW, Layer 2 returns ALLOW ---
    
    trap = trap_hooks.classify_request(ctx, session)
    if trap:
        session.mark_trapped(trap)
        resp = trap_hooks.handle_decoy(ctx, session)
        if resp:
            return resp
    
    upstream = await proxy(ctx)
    
    body = trap_hooks.transform_response(ctx, session, UpstreamResponse(upstream))
    
    log_event(ctx, session, "L1", "ALLOW", upstream.status_code, [])
    
    headers = dict(upstream.headers)
    headers.pop("content-length", None)
    headers.pop("transfer-encoding", None)
    headers.pop("content-encoding", None)
    
    return Response(content=body, status_code=upstream.status_code, headers=headers)
