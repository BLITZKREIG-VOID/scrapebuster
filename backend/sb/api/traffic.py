import json

from fastapi import APIRouter, Query

from ..contracts import TrafficEvent
from ..store.db import get_connection

router = APIRouter()

@router.get("/traffic/events")
async def get_traffic_events(after: int = Query(0, description="Sequence number to fetch after"), limit: int = Query(200, description="Max events to return")):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM traffic_events WHERE seq > ? ORDER BY seq ASC LIMIT ?",
            (after, limit)
        )
        rows = cursor.fetchall()
        
        events = []
        last_seq = after
        for row in rows:
            # Parse reasons from JSON
            reasons_raw = row["reasons"]
            reasons = json.loads(reasons_raw) if reasons_raw else []
            
            event = TrafficEvent(
                seq=row["seq"],
                event_id=row["event_id"],
                ts=row["ts"],
                session_id=row["session_id"],
                client_key=row["client_key"],
                ip=row["ip"],
                method=row["method"],
                path=row["path"],
                status_code=row["status_code"],
                user_agent=row["user_agent"],
                layer=row["layer"], # type: ignore
                decision=row["decision"], # type: ignore
                risk_score=row["risk_score"],
                reasons=reasons
            )
            events.append(event)
            last_seq = row["seq"]
            
        return {"events": events, "last_seq": last_seq}
    finally:
        conn.close()
