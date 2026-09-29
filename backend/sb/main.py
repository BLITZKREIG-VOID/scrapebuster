from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from .api.health import router as health_router
from .api.overview import router as overview_router
from .api.sessions import router as sessions_router
from .api.traffic import router as traffic_router
from .edge.pipeline import handle
from .trap import install as install_trap_hooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from .edge.proxy import _client
    if _client is not None:
        await _client.aclose()

app = FastAPI(title="ScapeBusters", lifespan=lifespan)
install_trap_hooks()

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(traffic_router, tags=["traffic"])
api_v1_router.include_router(sessions_router, tags=["sessions"])
api_v1_router.include_router(overview_router, tags=["overview"])
app.include_router(api_v1_router)

@app.api_route("/_sb/{path:path}", methods=["GET", "POST"])
async def sb_namespace(path: str, request: Request):
    if path == "static/challenge.js":
        import os

        from fastapi.responses import FileResponse
        js_path = os.path.join(os.path.dirname(__file__), "edge", "static", "challenge.js")
        return FileResponse(js_path, media_type="application/javascript")
            
    if path == "verify":
        from .edge.context import build_context
        from .edge.layer2 import verify_submission
        from .edge.pipeline import log_event
        from .edge.session import sessions
        from .edge.intel import record_decision
        from .store.sessions import save_session
        
        ctx = build_context(request)
        session = sessions.get_or_create(ctx)
        
        body = await request.json()
        cid = body.get("challenge_id")
        nonce = body.get("nonce")
        signals = body.get("signals", {})
        
        res = verify_submission(
            challenge_id=cid,
            nonce=nonce,
            signals=signals,
            session=session,
            request_ua=ctx.user_agent,
            elapsed_ms=signals.get("elapsed_ms", 0.0)
        )
        session.l2_score = res.score
        session.l2_signals = list(res.reasons)
        
        if res.band == "PASS" or res.band == "TRAP":
            if res.band == "PASS":
                session.state = "VERIFIED"
            else:
                session.state = "TRAPPED"
                
            response = JSONResponse({"status": "ok"})
            if res.clearance_cookie:
                response.headers["Set-Cookie"] = res.clearance_cookie
            log_event(ctx, session, "L2", res.band, 200, res.reasons, risk_score=res.score)
            record_decision(session, "L2", res.band)
            save_session(session)
            return response
            
        else:
            session.state = "RESTRICTED"
            log_event(ctx, session, "L2", "RESTRICT", 403, res.reasons, risk_score=res.score)
            record_decision(session, "L2", "RESTRICT")
            save_session(session)
            return JSONResponse({"status": "failed"}, status_code=403)
            
    # Legacy alias compatibility if needed
    if path == "challenge/verify":
        from .edge.context import build_context
        from .edge.layer2 import verify
        from .edge.pipeline import log_event
        from .edge.session import sessions
        from .edge.intel import record_decision
        from .store.sessions import save_session
        
        ctx = build_context(request)
        session = sessions.get_or_create(ctx)
        
        body = await request.json()
        cid = body.get("challenge_id")
        solution = body.get("solution")
        
        if verify(cid, solution, session):
            session.state = "VERIFIED"
            session.l2_score = 0
            session.l2_signals = []
            log_event(ctx, session, "L2", "PASS", 200, [])
            record_decision(session, "L2", "PASS")
            save_session(session)
            return JSONResponse({"status": "ok"})
        else:
            session.state = "RESTRICTED"
            session.l2_score = 100
            session.l2_signals = ["L2_POW_INVALID"]
            log_event(ctx, session, "L2", "RESTRICT", 403, session.l2_signals, risk_score=100)
            record_decision(session, "L2", "RESTRICT")
            save_session(session)
            return JSONResponse({"status": "failed"}, status_code=403)
            
    return JSONResponse(content={"msg": f"SB stub for {path}"})

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def catch_all(path: str, request: Request):
    # Route through the edge pipeline
    return await handle(request)
