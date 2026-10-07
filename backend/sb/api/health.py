from fastapi import APIRouter

from ..contracts import Health
from ..store.db import get_connection

router = APIRouter()

@router.get("/health", response_model=Health)
async def get_health():
    db_status = "ok"
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception:
        db_status = "down"

    if db_status == "ok":
        try:
            from ..store.ledger import verify_chain

            chain_info = verify_chain()
            if chain_info.get("result") != "VALID":
                db_status = "down"
        except Exception:
            db_status = "down"

    # These dependencies are intentionally left unprobed until the owners
    # provide their runtime configuration and health interfaces.
    return Health(
        status="ok" if db_status == "ok" else "degraded",
        components={
            "db": db_status,
            "upstream": "not_checked",
            "llm": "not_checked",
            "s3": "not_checked",
        },
    )
