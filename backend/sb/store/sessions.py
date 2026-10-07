"""SQLite persistence helpers for edge session profiles."""

from __future__ import annotations

import inspect
import json
import sqlite3
from typing import Any

from .db import get_connection
from .ledger import append_event


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def _decode(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def save_session(session: Any) -> None:
    """Insert or update one session without replacing its original first_seen.

    Appends an authoritative snapshot of the session state to the append-only forensic ledger.
    """
    conn = get_connection()
    try:
        session_id = session.session_id
        client_key = getattr(session, "client_key", "")
        ip = getattr(session, "ip", "")
        user_agent = getattr(session, "user_agent", "")
        header_fp = getattr(session, "header_fp", "")
        first_seen = getattr(session, "first_seen", "")
        last_seen = getattr(session, "last_seen", "")
        request_count = getattr(session, "request_count", 0)
        state = getattr(session, "state", "SANDBOX")
        classification = getattr(session, "classification", "UNKNOWN")
        decision = getattr(session, "decision", "SANDBOX")
        risk_score = getattr(session, "risk_score", 0)
        reasons = getattr(session, "reasons", [])
        pages = getattr(session, "pages", [])
        traps_triggered = getattr(session, "traps_triggered", getattr(session, "offenses_triggered", []))
        canaries_exposed = getattr(session, "canaries_exposed", [])
        event_ids = getattr(session, "event_ids", [])

        conn.execute(
            """INSERT INTO sessions (
                   session_id, client_key, ip, user_agent, header_fp,
                   first_seen, last_seen, request_count, state, classification,
                   decision, risk_score, reasons, pages,
                   traps_triggered, canaries_exposed, event_ids
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                   client_key=excluded.client_key,
                   ip=excluded.ip,
                   user_agent=excluded.user_agent,
                   header_fp=excluded.header_fp,
                   first_seen=CASE WHEN sessions.first_seen='' THEN excluded.first_seen
                                   ELSE sessions.first_seen END,
                   last_seen=excluded.last_seen,
                   request_count=excluded.request_count,
                   state=excluded.state,
                   classification=excluded.classification,
                   decision=excluded.decision,
                   risk_score=excluded.risk_score,
                   reasons=excluded.reasons,
                   pages=excluded.pages,
                   traps_triggered=excluded.traps_triggered,
                   canaries_exposed=excluded.canaries_exposed,
                   event_ids=excluded.event_ids""",
            (
                session_id,
                client_key,
                ip,
                user_agent,
                header_fp,
                first_seen,
                last_seen,
                request_count,
                state,
                classification,
                decision,
                risk_score,
                _json(reasons),
                _json(pages),
                _json(traps_triggered),
                _json(canaries_exposed),
                _json(event_ids),
            ),
        )
        conn.commit()

        # Query authoritative first_seen if previously preserved in database
        saved_row = conn.execute(
            "SELECT first_seen FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        authoritative_first_seen = saved_row["first_seen"] if saved_row else first_seen
    finally:
        conn.close()

    # Append authoritative snapshot to the append-only forensic ledger
    snapshot = {
        "session_id": session_id,
        "client_key": client_key,
        "ip": ip,
        "user_agent": user_agent,
        "header_fp": header_fp,
        "first_seen": authoritative_first_seen,
        "last_seen": last_seen,
        "request_count": request_count,
        "state": state,
        "classification": classification,
        "decision": decision,
        "risk_score": risk_score,
        "reasons": reasons,
        "pages": pages,
        "traps_triggered": traps_triggered,
        "canaries_exposed": canaries_exposed,
        "event_ids": event_ids,
    }
    append_event("session_snapshot", snapshot)


def _session_from_row(row: sqlite3.Row):
    # Local import avoids coupling the store module to the edge at import time.
    from ..edge.session import Session

    reasons = _decode(row["reasons"] if "reasons" in row.keys() else None, [])
    pages = _decode(row["pages"] if "pages" in row.keys() else None, [])
    traps = _decode(row["traps_triggered"] if "traps_triggered" in row.keys() else None, [])
    canaries = _decode(row["canaries_exposed"] if "canaries_exposed" in row.keys() else None, [])
    event_ids = _decode(row["event_ids"] if "event_ids" in row.keys() else None, [])

    row_data = {
        "session_id": row["session_id"],
        "client_key": row["client_key"] if "client_key" in row.keys() else "",
        "ip": (row["ip"] if "ip" in row.keys() else "") or "",
        "user_agent": (row["user_agent"] if "user_agent" in row.keys() else "") or "",
        "header_fp": (row["header_fp"] if "header_fp" in row.keys() else "") or "",
        "first_seen": (row["first_seen"] if "first_seen" in row.keys() else "") or "",
        "last_seen": (row["last_seen"] if "last_seen" in row.keys() else "") or "",
        "request_count": (row["request_count"] if "request_count" in row.keys() else 0) or 0,
        "state": (row["state"] if "state" in row.keys() else "SANDBOX") or "SANDBOX",
        "classification": (row["classification"] if "classification" in row.keys() else "UNKNOWN") or "UNKNOWN",
        "decision": (row["decision"] if "decision" in row.keys() else "SANDBOX") or "SANDBOX",
        "risk_score": (row["risk_score"] if "risk_score" in row.keys() else 0) or 0,
        "reasons": reasons,
        "pages": pages,
        "traps_triggered": traps,
        "canaries_exposed": canaries,
        "event_ids": event_ids,
    }

    sig = inspect.signature(Session)
    kwargs = {}
    for param_name, param in sig.parameters.items():
        if param_name in row_data:
            kwargs[param_name] = row_data[param_name]
        elif param.default is not inspect.Parameter.empty:
            kwargs[param_name] = param.default
        else:
            kwargs[param_name] = ""
    sess = Session(**kwargs)
    for k, v in row_data.items():
        if not hasattr(sess, k):
            setattr(sess, k, v)
    return sess


def get_session(session_id: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return _session_from_row(row) if row else None
    finally:
        conn.close()


def list_sessions(classification: str | None = None):
    conn = get_connection()
    try:
        if classification:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE classification = ? ORDER BY last_seen DESC",
                (classification,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY last_seen DESC"
            ).fetchall()
        return [_session_from_row(row) for row in rows]
    finally:
        conn.close()
