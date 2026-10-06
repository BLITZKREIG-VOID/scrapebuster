"""Demo control API — honest neutral local reset and status."""
from __future__ import annotations

import uuid
from fastapi import APIRouter
from sb.contracts import DemoResetCheck, DemoResetResponse, DemoStatus
from sb.store import db

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/reset", response_model=DemoResetResponse)
def post_reset() -> DemoResetResponse:
    """Reset local SQLite state and initialize fresh run_id."""
    db.reset_db()
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    with db.get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO demo_state (key, value) VALUES ('run_id', ?)", (run_id,))
        conn.execute("INSERT OR REPLACE INTO demo_state (key, value) VALUES ('phase', ?)", ("READY",))
        conn.commit()
    return DemoResetResponse(
        ok=True,
        run_id=run_id,
        checks=[DemoResetCheck(name="database", ok=True, detail="Database reset complete.")],
    )


@router.get("/status", response_model=DemoStatus)
def get_status() -> DemoStatus:
    """Return current run ID and phase."""
    try:
        with db.get_connection() as conn:
            row_run = conn.execute("SELECT value FROM demo_state WHERE key='run_id'").fetchone()
            row_phase = conn.execute("SELECT value FROM demo_state WHERE key='phase'").fetchone()
        run_id = row_run["value"] if row_run else None
        phase = row_phase["value"] if row_phase else "READY"
    except Exception:
        run_id = None
        phase = "READY"

    if phase not in ("READY", "RUNNING", "COMPLETE", "PAUSED", "FAILED"):
        phase = "READY"

    return DemoStatus(
        run_id=run_id,
        phase=phase,
        mode="live",
        steps=[],
    )
