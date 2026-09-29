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
    return SessionDetail(
        **_summary(session).model_dump(),
        client_key=session.client_key,
        ip=session.ip,
        user_agent=session.user_agent,
        header_fp=session.header_fp,
        first_seen=session.first_seen,
        last_seen=session.last_seen,
        l1_score=session.l1_score,
        l1_reasons=session.l1_reasons,
        l2_score=session.l2_score,
        l2_signals=session.l2_signals,
        layer_path=session.layer_path,
        pages=session.pages,
        traps_triggered=session.traps_triggered,
        canaries_exposed=session.canaries_exposed,
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
