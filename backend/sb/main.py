import logging
import sqlite3
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request

from .api.callbacks import router as callbacks_router
from .api.canaries import router as canaries_router
from .api.cases import router as cases_router
from .api.classifier import router as classifier_router
from .api.datasets import router as datasets_router
from .api.health import router as health_router
from .api.overview import router as overview_router
from .api.probes import router as probes_router
from .api.sessions import router as sessions_router
from .api.traffic import router as traffic_router
from .edge.pipeline import handle
from .kb.ingest import router as kb_router

logger = logging.getLogger("sb.main")

try:
    from .api.demo import router as demo_router
except ImportError:
    demo_router = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: validate config, initialize DB, install hooks, manage telemetry worker, cleanup on shutdown."""
    from .config import validate_required_urls
    from .edge.proxy import close_client
    from .edge.telemetry import TelemetryTap
    from .offense import install as install_offense_hooks
    from .store.db import init_db

    try:
        # Enforce canonical SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL (PRD PR-2)
        validate_required_urls()

        # Ensure schema, ledger, and triggers are initialized before first request/verify
        # Startup corrupt-store must not crash application (best-effort degraded origin operation)
        try:
            init_db()
        except (sqlite3.Error, OSError) as db_err:
            logger.error("Database initialization failed at startup (store degraded): %s", db_err)

        # Install W2 offense hooks
        install_offense_hooks()

        # Start background telemetry tap worker (PRD FR1.1, FR1.4)
        await TelemetryTap.start()

        yield
    finally:
        # Gracefully flush and stop background telemetry worker
        try:
            await TelemetryTap.stop()
        except (sqlite3.Error, OSError, RuntimeError) as tap_stop_err:
            logger.error("Error stopping TelemetryTap: %s", tap_stop_err)
        await close_client()


app = FastAPI(title="ScapeBusters", lifespan=lifespan)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(traffic_router, tags=["traffic"])
api_v1_router.include_router(sessions_router, tags=["sessions"])
api_v1_router.include_router(classifier_router, tags=["classifier"])
api_v1_router.include_router(overview_router, tags=["overview"])
api_v1_router.include_router(canaries_router, tags=["canaries"])
api_v1_router.include_router(datasets_router, tags=["datasets"])
api_v1_router.include_router(probes_router, tags=["probes"])
api_v1_router.include_router(cases_router, tags=["cases"])
api_v1_router.include_router(kb_router, tags=["kb"])
api_v1_router.include_router(callbacks_router, tags=["callbacks"])
app.include_router(api_v1_router)

# Mount demo control API if available (W4 rewrites demo API)
if demo_router is not None:
    app.include_router(demo_router)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def catch_all(path: str, request: Request):
    """Route all proxied traffic through the edge pipeline."""
    return await handle(request)
