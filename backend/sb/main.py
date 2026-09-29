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
            
    if path == "challenge/verify":
        from .edge.context import build_context
        from .edge.layer2 import verify
        from .edge.session import sessions
        
        ctx = build_context(request)
        session = sessions.get_or_create(ctx)
        
        body = await request.json()
        cid = body.get("challenge_id")
        solution = body.get("solution")
        
        if verify(cid, solution, session):
            session.state = "VERIFIED"
            return JSONResponse({"status": "ok"})
        else:
            session.state = "SUSPICIOUS"
            return JSONResponse({"status": "failed"}, status_code=403)
            
    return JSONResponse(content={"msg": f"SB stub for {path}"})

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def catch_all(path: str, request: Request):
    # Route through the edge pipeline
    return await handle(request)
