
from fastapi import APIRouter

from ..edge.session import sessions
from ..store.db import get_connection

router = APIRouter()

@router.get("/overview")
async def get_overview():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Get run_id
        cursor.execute("SELECT value FROM demo_state WHERE key='run_id'")
        row = cursor.fetchone()
        run_id = row["value"] if row else "NO_RUN_ID"
        
        # Get counts from traffic_events
        cursor.execute("SELECT decision, COUNT(*) as cnt FROM traffic_events GROUP BY decision")
        decision_rows = cursor.fetchall()
        counts = {
            "ALLOW": 0, "ESCALATE": 0, "CHALLENGE": 0, "PASS": 0, 
            "RESTRICT": 0, "THROTTLE": 0, "BLOCK": 0, "TRAP": 0
        }
        for dr in decision_rows:
            if dr["decision"] in counts:
                counts[dr["decision"]] = dr["cnt"]
                
        # Ladder aggregation
        ladder = {
            "safe": counts["ALLOW"] + counts["PASS"],
            "suspicious": counts["ESCALATE"],
            "challenge_restrict": counts["CHALLENGE"] + counts["RESTRICT"],
            "block": counts["THROTTLE"] + counts["BLOCK"],
            "trap": counts["TRAP"],
            "provenance": 0 # Not implemented yet
        }
        
        # Sessions aggregation from memory
        sessions_by_class = {}
        for s in sessions._sessions.values():
            c = s.classification
            sessions_by_class[c] = sessions_by_class.get(c, 0) + 1
            
        return {
            "run_id": run_id,
            "counts": counts,
            "ladder": ladder,
            "sessions_by_class": sessions_by_class,
            "canaries": {"active": 0, "exposed": 0, "observed": 0},
            "cases": {"total": 0, "detected": 0},
            "pipeline": [
                {"stage": "edge", "status": "ok"},
                {"stage": "trap", "status": "ok"}
            ],
            "latest_case": None
        }
    finally:
        conn.close()
