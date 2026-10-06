from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from .api.canaries import router as canaries_router
from .api.cases import router as cases_router
from .api.datasets import router as datasets_router
from .api.health import router as health_router
from .api.overview import router as overview_router
from .api.probes import router as probes_router
from .api.sessions import router as sessions_router
from .api.traffic import router as traffic_router
from .edge.pipeline import handle

try:
    from .api.demo import router as demo_router
except ImportError:
    demo_router = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from .edge.proxy import _client

    if _client is not None:
        await _client.aclose()


app = FastAPI(title="ScapeBusters", lifespan=lifespan)

# Install offense / trap hooks
try:
    from .offense import install as install_offense_hooks

    install_offense_hooks()
except ImportError:
    try:
        from .trap import install as install_trap_hooks

        install_trap_hooks()
    except ImportError:
        pass

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(traffic_router, tags=["traffic"])
api_v1_router.include_router(sessions_router, tags=["sessions"])
api_v1_router.include_router(overview_router, tags=["overview"])
api_v1_router.include_router(canaries_router, tags=["canaries"])
api_v1_router.include_router(datasets_router, tags=["datasets"])
api_v1_router.include_router(probes_router, tags=["probes"])
api_v1_router.include_router(cases_router, tags=["cases"])
app.include_router(api_v1_router)

# Mount demo control API if available (W4 rewrites demo API)
if demo_router is not None:
    app.include_router(demo_router)


@app.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def api_v1_not_found(path: str):
    """Keep unknown versioned API paths inside the control plane."""
    return JSONResponse(content={"detail": "Not Found"}, status_code=404)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def catch_all(path: str, request: Request):
    """Route all proxied traffic through the edge pipeline."""
    return await handle(request)
