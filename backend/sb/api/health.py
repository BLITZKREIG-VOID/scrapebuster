from fastapi import APIRouter

from ..contracts import Health
from ..store.db import get_connection

router = APIRouter()


@router.get("/health", response_model=Health)
async def get_health() -> Health:
    # 1. Database connectivity
    db_status = "ok"
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception:
        db_status = "down"

    # 2. Forensic ledger chain integrity
    ledger_status = "ok"
    if db_status == "ok":
        try:
            from ..store.ledger import verify_chain

            chain_info = verify_chain()
            if chain_info.get("result") != "VALID":
                ledger_status = "down"
                db_status = "down"
        except Exception:
            ledger_status = "down"
            db_status = "down"
    else:
        ledger_status = "down"

    # 3. Telemetry queue health
    queue_status = "ok"
    try:
        from ..edge.telemetry import TelemetryTap

        if hasattr(TelemetryTap, "get_status"):
            queue_status = TelemetryTap.get_status()
        elif hasattr(TelemetryTap, "_queue"):
            q = getattr(TelemetryTap, "_queue")
            if q is not None and hasattr(q, "full") and q.full():
                queue_status = "degraded"
    except Exception:
        queue_status = "ok"

    # 4. Upstream origin configuration
    upstream_status = "not_checked"
    try:
        from ..config import SB_UPSTREAM_ORIGIN

        if not SB_UPSTREAM_ORIGIN:
            upstream_status = "not_checked"
        else:
            upstream_status = "ok"
    except Exception:
        upstream_status = "not_checked"

    overall_status = "ok"
    if db_status != "ok" or ledger_status != "ok" or queue_status == "down":
        overall_status = "degraded"

    return Health(
        status=overall_status,
        components={
            "db": db_status,
            "ledger": ledger_status,
            "telemetry_queue": queue_status,
            "upstream": upstream_status,
            "llm": "not_checked",
            "s3": "not_checked",
        },
    )
