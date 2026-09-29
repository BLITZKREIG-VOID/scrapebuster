
from fastapi import APIRouter, HTTPException

from ..contracts import SessionDetail, SessionSummary
from ..edge.session import sessions

router = APIRouter()

@router.get("/sessions")
async def get_sessions(classification: str | None = None):
    result = []
    # sessions._sessions is a dict of sid -> Session
    for session_obj in sessions._sessions.values():
        if classification and session_obj.classification != classification:
            continue
        
        summary = SessionSummary(
            session_id=session_obj.session_id,
            classification=session_obj.classification,
            request_count=len(session_obj.layer_path), # Simplified, normally would be tracked
            state=session_obj.state
        )
        result.append(summary)
        
    return {"sessions": result}

@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(session_id: str):
    if session_id not in sessions._sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session_obj = sessions._sessions[session_id]
    
    # Normally we'd get some of this from DB or full session state
    # For INT-05, we return the data available in memory/stubbed
    detail = SessionDetail(
        session_id=session_obj.session_id,
        classification=session_obj.classification,
        request_count=len(session_obj.layer_path),
        state=session_obj.state,
        client_key=session_obj.client_key,
        ip="127.0.0.1", # Normally stored in session profile
        user_agent="", # Normally stored
        header_fp="", # Normally stored
        first_seen="", # Normally tracked
        last_seen="",
        l1_score=session_obj.l1_score,
        l1_reasons=[],
        l2_score=session_obj.l2_score,
        l2_signals=[],
        layer_path=session_obj.layer_path,
        pages=[],
        traps_triggered=[],
        canaries_exposed=[]
    )
    return detail
