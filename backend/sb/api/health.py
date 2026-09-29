import sqlite3

from fastapi import APIRouter

from ..contracts import Health
from ..store.db import get_connection

router = APIRouter()

@router.get("/health", response_model=Health)
async def get_health():
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        db_status = "ok"
    except sqlite3.Error:
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
