from fastapi import APIRouter

from ..contracts import Overview, PipelineStage
from ..store.db import get_connection

router = APIRouter()

DECISIONS = (
    "ALLOW",
    "ESCALATE",
    "CHALLENGE",
    "PASS",
    "RESTRICT",
    "THROTTLE",
    "BLOCK",
    "TRAP",
)


@router.get("/overview", response_model=Overview)
async def get_overview() -> Overview:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM demo_state WHERE key='run_id'"
        ).fetchone()
        run_id = row["value"] if row else "NO_RUN_ID"

        counts = {decision: 0 for decision in DECISIONS}
        for result in conn.execute(
            "SELECT decision, COUNT(*) AS count FROM traffic_events GROUP BY decision"
        ).fetchall():
            if result["decision"] in counts:
                counts[result["decision"]] = result["count"]

        sessions_by_class = {
            row["classification"]: row["count"]
            for row in conn.execute(
                """SELECT classification, COUNT(*) AS count
                   FROM sessions GROUP BY classification"""
            ).fetchall()
        }

        canary_counts = {"active": 0, "exposed": 0, "observed": 0}
        for result in conn.execute(
            "SELECT status, COUNT(*) AS count FROM canaries GROUP BY status"
        ).fetchall():
            key = str(result["status"]).lower()
            if key in canary_counts:
                canary_counts[key] = result["count"]

        case_total = conn.execute("SELECT COUNT(*) AS count FROM cases").fetchone()["count"]
        case_detected = conn.execute(
            "SELECT COUNT(*) AS count FROM cases WHERE status = 'PROVENANCE_SIGNAL_DETECTED'"
        ).fetchone()["count"]
        latest_row = conn.execute(
            """SELECT case_id, run_id, created_at, status, confidence, primary_canary_id
               FROM cases ORDER BY created_at DESC, case_id DESC LIMIT 1"""
        ).fetchone()
        latest_case = dict(latest_row) if latest_row else None

    finally:
        conn.close()

    ladder = {
        "safe": counts["ALLOW"] + counts["PASS"],
        "suspicious": counts["ESCALATE"],
        "challenge_restrict": counts["CHALLENGE"] + counts["RESTRICT"],
        "block": counts["THROTTLE"] + counts["BLOCK"],
        "trap": counts["TRAP"],
        "provenance": case_detected,
    }

    return Overview(
        run_id=run_id,
        counts=counts,
        ladder=ladder,
        sessions_by_class=sessions_by_class,
        canaries=canary_counts,
        cases={"total": case_total, "detected": case_detected},
        pipeline=[
            PipelineStage(stage="edge", status="ok"),
            PipelineStage(stage="trap", status="unknown"),
            PipelineStage(stage="provenance", status="unknown"),
        ],
        latest_case=latest_case,
    )
