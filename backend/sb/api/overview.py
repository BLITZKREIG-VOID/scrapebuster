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
    finally:
        conn.close()

    ladder = {
        "safe": counts["ALLOW"] + counts["PASS"],
        "suspicious": counts["ESCALATE"],
        "challenge_restrict": counts["CHALLENGE"] + counts["RESTRICT"],
        "block": counts["THROTTLE"] + counts["BLOCK"],
        "trap": counts["TRAP"],
        # Provenance is owned by another subsystem and is not aggregated here.
        "provenance": None,
    }

    return Overview(
        run_id=run_id,
        counts=counts,
        ladder=ladder,
        sessions_by_class=sessions_by_class,
        # None means the API has not integrated those owner-managed sources yet;
        # zero would incorrectly imply that the source was queried successfully.
        canaries={"active": None, "exposed": None, "observed": None},
        cases={"total": None, "detected": None},
        pipeline=[
            PipelineStage(stage="edge", status="ok"),
            PipelineStage(stage="trap", status="unknown"),
            PipelineStage(stage="provenance", status="unknown"),
        ],
        latest_case=None,
    )
