"""SQLite persistence helpers for edge session profiles."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .db import get_connection


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
    """Insert or update one session without replacing its original first_seen."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO sessions (
                   session_id, client_key, ip, user_agent, header_fp,
                   first_seen, last_seen, request_count, state, classification,
                   l1_score, l1_reasons, l2_score, l2_signals, layer_path,
                   pages, traps_triggered, canaries_exposed, block_until
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                   l1_score=excluded.l1_score,
                   l1_reasons=excluded.l1_reasons,
                   l2_score=excluded.l2_score,
                   l2_signals=excluded.l2_signals,
                   layer_path=excluded.layer_path,
                   pages=excluded.pages,
                   traps_triggered=excluded.traps_triggered,
                   canaries_exposed=excluded.canaries_exposed,
                   block_until=excluded.block_until""",
            (
                session.session_id,
                session.client_key,
                session.ip,
                session.user_agent,
                session.header_fp,
                session.first_seen,
                session.last_seen,
                session.request_count,
                session.state,
                session.classification,
                session.l1_score,
                _json(session.l1_reasons),
                session.l2_score,
                _json(session.l2_signals),
                _json(session.layer_path),
                _json(session.pages),
                _json(session.traps_triggered),
                _json(session.canaries_exposed),
                session.block_until,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _session_from_row(row: sqlite3.Row):
    # Local import avoids coupling the store module to the edge at import time.
    from ..edge.session import Session

    return Session(
        session_id=row["session_id"],
        client_key=row["client_key"],
        ip=row["ip"] or "",
        user_agent=row["user_agent"] or "",
        header_fp=row["header_fp"] or "",
        first_seen=row["first_seen"] or "",
        last_seen=row["last_seen"] or "",
        request_count=row["request_count"] or 0,
        state=row["state"] or "NEW",
        classification=row["classification"] or "UNKNOWN",
        l1_score=row["l1_score"] or 0,
        l1_reasons=_decode(row["l1_reasons"], []),
        l2_score=row["l2_score"] or 0,
        l2_signals=_decode(row["l2_signals"], []),
        layer_path=_decode(row["layer_path"], []),
        pages=_decode(row["pages"], []),
        traps_triggered=_decode(row["traps_triggered"], []),
        canaries_exposed=_decode(row["canaries_exposed"], []),
        block_until=row["block_until"] or "",
    )


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
