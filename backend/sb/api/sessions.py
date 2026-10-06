from fastapi import APIRouter, HTTPException, Query

from ..contracts import SessionDetail, SessionList, SessionSummary
from ..store.sessions import get_session, list_sessions

router = APIRouter()


def _summary(session) -> SessionSummary:
    return SessionSummary(
        session_id=session.session_id,
        classification=session.classification,
        request_count=session.request_count,
        state=session.state,
    )


def _detail(session) -> SessionDetail:
    decision = getattr(session, "decision", "SANDBOX")
    if decision not in ("FAST_PATH", "SANDBOX"):
        decision = "SANDBOX"
    return SessionDetail(
        **_summary(session).model_dump(),
        client_key=getattr(session, "client_key", "") or "",
        ip=getattr(session, "ip", "") or "",
        user_agent=getattr(session, "user_agent", "") or "",
        header_fp=getattr(session, "header_fp", "") or "",
        first_seen=getattr(session, "first_seen", "") or "",
        last_seen=getattr(session, "last_seen", "") or "",
        decision=decision,
        risk_score=getattr(session, "risk_score", 0) or 0,
        reasons=getattr(session, "reasons", []) or [],
        pages=getattr(session, "pages", []) or [],
        traps_triggered=getattr(session, "traps_triggered", getattr(session, "offenses_triggered", [])) or [],
        canaries_exposed=getattr(session, "canaries_exposed", []) or [],
        event_ids=getattr(session, "event_ids", []) or [],
    )


@router.get("/sessions", response_model=SessionList)
async def get_sessions(
    classification: str | None = Query(default=None),
) -> SessionList:
    return SessionList(
        sessions=[_summary(session) for session in list_sessions(classification)]
    )


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(session_id: str) -> SessionDetail:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _detail(session)
