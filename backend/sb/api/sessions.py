from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException, Query

from ..contracts import SessionDetail, SessionList, SessionSummary
from ..store.db import get_connection

router = APIRouter()


def _row_to_summary(row: dict) -> SessionSummary:
    client_ip = row.get("client_ip") or row.get("ip") or ""
    return SessionSummary(
        session_id=str(row["session_id"]),
        classification=str(row.get("classification") or "UNKNOWN"),
        request_count=int(row.get("request_count") or 0),
        state=str(row.get("state") or "SANDBOX"),
        client_ip=client_ip,
        asset_ratio=float(row.get("asset_ratio") or 0.0),
        trust_score=float(row.get("trust_score") or 0.0),
    )


def _row_to_detail(row: dict) -> SessionDetail:
    client_ip = row.get("client_ip") or row.get("ip") or ""
    asn_val = row.get("asn")
    if asn_val is not None:
        try:
            asn_val = int(asn_val)
        except (ValueError, TypeError):
            asn_val = None

    def _parse_list(key: str) -> list[str]:
        raw = row.get(key)
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return []
        if isinstance(raw, list):
            return raw
        return []

    traps = _parse_list("traps_triggered")
    if not traps:
        traps = _parse_list("offenses_triggered")

    raw_decision = str(row.get("decision") or "SANDBOX")
    decision_val = raw_decision if raw_decision in ("FAST_PATH", "SANDBOX") else "SANDBOX"
    trust_score_val = float(row.get("trust_score") or 0.0)

    sid = str(row["session_id"])
    active_sess = None
    try:
        from ..edge.session import sessions

        active_sess = sessions.get(sid)
    except Exception:
        pass

    ar_decision = (
        getattr(active_sess, "ar_classifier_decision", None)
        or row.get("ar_classifier_decision")
        or decision_val
    )
    conf_score = getattr(active_sess, "confidence_score", None)
    if conf_score is None and row.get("confidence_score") is not None:
        try:
            conf_score = float(row["confidence_score"])
        except Exception:
            conf_score = None
    if conf_score is None:
        conf_score = round(trust_score_val / 100.0, 2)

    r_decision = (
        getattr(active_sess, "router_decision", None)
        or row.get("router_decision")
        or decision_val
    )

    return SessionDetail(
        session_id=sid,
        classification=str(row.get("classification") or "UNKNOWN"),
        request_count=int(row.get("request_count") or 0),
        state=str(row.get("state") or "SANDBOX"),
        client_key=str(row.get("client_key") or ""),
        client_ip=client_ip,
        ip=client_ip,
        asn=asn_val,
        asn_status=str(row.get("asn_status") or "unavailable"),
        ja3_hash=row.get("ja3_hash"),
        ja4_hash=row.get("ja4_hash"),
        tls_source=str(row.get("tls_source") or "none"),
        user_agent=str(row.get("user_agent") or ""),
        header_fp=str(row.get("header_fp") or ""),
        first_seen=str(row.get("first_seen") or ""),
        last_seen=str(row.get("last_seen") or ""),
        static_count=int(row.get("static_count") or 0),
        api_count=int(row.get("api_count") or 0),
        asset_ratio=float(row.get("asset_ratio") or 0.0),
        trust_score=trust_score_val,
        ar_classifier_decision=ar_decision,
        confidence_score=conf_score,
        router_decision=r_decision,
        decision=decision_val,
        risk_score=int(row.get("risk_score") or 0),
        reasons=_parse_list("reasons"),
        pages=_parse_list("pages"),
        traps_triggered=traps,
        canaries_exposed=_parse_list("canaries_exposed"),
        event_ids=_parse_list("event_ids"),
    )


@router.get("/sessions", response_model=SessionList)
async def get_sessions(
    classification: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> SessionList:
    try:
        from ..edge.telemetry import TelemetryTap

        await TelemetryTap.flush()
    except Exception:
        pass

    conn = get_connection()
    try:
        if classification:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE classification = ? ORDER BY last_seen DESC LIMIT ? OFFSET ?",
                (classification, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY last_seen DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return SessionList(sessions=[_row_to_summary(dict(r)) for r in rows])
    finally:
        conn.close()


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(session_id: str) -> SessionDetail:
    try:
        from ..edge.telemetry import TelemetryTap

        await TelemetryTap.flush()
    except Exception:
        pass

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        return _row_to_detail(dict(row))
    finally:
        conn.close()
