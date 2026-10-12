"""SQLite persistence helpers for edge session profiles in ScrapeBuster Phase 1."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from .db import get_connection
from .models import Session

logger = logging.getLogger("sb.store.sessions")


def _json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))


def _decode(value: Any, default: Any) -> Any:
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _session_to_dict(sess: Any) -> dict[str, Any]:
    if isinstance(sess, dict):
        return dict(sess)
    if hasattr(sess, "to_dict"):
        return sess.to_dict()
    if hasattr(sess, "to_snapshot"):
        return sess.to_snapshot()
    if hasattr(sess, "__dict__"):
        return dict(sess.__dict__)
    return dict(sess)


def _format_session_row(sess: Any) -> tuple:
    data = _session_to_dict(sess)

    session_id = str(data.get("session_id") or "")
    client_key = str(data.get("client_key") or "")
    client_ip = str(data.get("client_ip") or data.get("ip") or "")
    ip = client_ip

    asn_val = data.get("asn")
    if asn_val is not None:
        try:
            asn_int = int(asn_val)
        except (ValueError, TypeError):
            asn_int = None
    else:
        asn_int = None

    asn_status = str(data.get("asn_status") or "unavailable")
    ja3_hash = str(data.get("ja3_hash")) if data.get("ja3_hash") else None
    ja4_hash = str(data.get("ja4_hash")) if data.get("ja4_hash") else None
    tls_source = str(data.get("tls_source") or "none")
    user_agent = str(data.get("user_agent") or "")
    header_fp = str(data.get("header_fp") or "")
    first_seen = str(data.get("first_seen") or "")
    last_seen = str(data.get("last_seen") or "")
    request_count = int(data.get("request_count") or 0)
    static_count = int(data.get("static_count") or 0)
    api_count = int(data.get("api_count") or 0)
    
    asset_ratio_val = data.get("asset_ratio")
    if asset_ratio_val is not None:
        try:
            asset_ratio = round(float(asset_ratio_val), 4)
        except (ValueError, TypeError):
            asset_ratio = round(float(static_count) / max(1, api_count), 4)
    else:
        asset_ratio = round(float(static_count) / max(1, api_count), 4)

    state = str(data.get("state") or "SANDBOX")
    classification = str(data.get("classification") or "UNKNOWN")
    decision = str(data.get("decision") or "SANDBOX")
    risk_score = int(data.get("risk_score") or 0)
    trust_score = float(data.get("trust_score") or 0.0)
    ar_anomaly_streak = int(data.get("ar_anomaly_streak") or 0)
    locked_sandbox = 1 if data.get("locked_sandbox") else 0
    reasons = _json(data.get("reasons") or [])
    pages = _json(data.get("pages") or [])
    traps = _json(data.get("traps_triggered") or data.get("offenses_triggered") or [])
    canaries = _json(data.get("canaries_exposed") or [])
    event_ids = _json(data.get("event_ids") or [])

    return (
        session_id,
        client_key,
        client_ip,
        ip,
        asn_int,
        asn_status,
        ja3_hash,
        ja4_hash,
        tls_source,
        user_agent,
        header_fp,
        first_seen,
        last_seen,
        request_count,
        static_count,
        api_count,
        asset_ratio,
        trust_score,
        ar_anomaly_streak,
        locked_sandbox,
        state,
        classification,
        decision,
        risk_score,
        reasons,
        pages,
        traps,
        canaries,
        event_ids,
    )


UPSERT_SESSION_SQL = """
INSERT INTO sessions (
    session_id, client_key, client_ip, ip, asn, asn_status,
    ja3_hash, ja4_hash, tls_source, user_agent, header_fp,
    first_seen, last_seen, request_count, static_count, api_count, asset_ratio,
    trust_score, ar_anomaly_streak, locked_sandbox,
    state, classification, decision, risk_score,
    reasons, pages, traps_triggered, canaries_exposed, event_ids
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(session_id) DO UPDATE SET
    client_key = CASE WHEN excluded.client_key != '' THEN excluded.client_key ELSE sessions.client_key END,
    client_ip = CASE WHEN excluded.client_ip != '' THEN excluded.client_ip ELSE sessions.client_ip END,
    ip = CASE WHEN excluded.client_ip != '' THEN excluded.client_ip ELSE sessions.ip END,
    asn = CASE WHEN excluded.asn IS NOT NULL THEN excluded.asn ELSE sessions.asn END,
    asn_status = CASE WHEN excluded.asn_status != '' AND excluded.asn_status != 'unavailable' THEN excluded.asn_status ELSE sessions.asn_status END,
    ja3_hash = CASE WHEN excluded.ja3_hash IS NOT NULL THEN excluded.ja3_hash ELSE sessions.ja3_hash END,
    ja4_hash = CASE WHEN excluded.ja4_hash IS NOT NULL THEN excluded.ja4_hash ELSE sessions.ja4_hash END,
    tls_source = CASE WHEN excluded.tls_source != '' AND excluded.tls_source != 'none' THEN excluded.tls_source ELSE sessions.tls_source END,
    user_agent = CASE WHEN excluded.user_agent != '' THEN excluded.user_agent ELSE sessions.user_agent END,
    header_fp = CASE WHEN excluded.header_fp != '' THEN excluded.header_fp ELSE sessions.header_fp END,
    first_seen = CASE WHEN sessions.first_seen = '' OR sessions.first_seen IS NULL THEN excluded.first_seen ELSE sessions.first_seen END,
    last_seen = excluded.last_seen,
    request_count = MAX(sessions.request_count, excluded.request_count),
    static_count = MAX(sessions.static_count, excluded.static_count),
    api_count = MAX(sessions.api_count, excluded.api_count),
    asset_ratio = excluded.asset_ratio,
    trust_score = excluded.trust_score,
    ar_anomaly_streak = excluded.ar_anomaly_streak,
    locked_sandbox = MAX(sessions.locked_sandbox, excluded.locked_sandbox),
    state = CASE WHEN excluded.state != '' THEN excluded.state ELSE sessions.state END,
    classification = CASE WHEN excluded.classification != '' AND excluded.classification != 'UNKNOWN' THEN excluded.classification ELSE sessions.classification END,
    decision = CASE WHEN excluded.decision != '' THEN excluded.decision ELSE sessions.decision END,
    risk_score = MAX(sessions.risk_score, excluded.risk_score),
    reasons = excluded.reasons,
    pages = excluded.pages,
    traps_triggered = excluded.traps_triggered,
    canaries_exposed = excluded.canaries_exposed,
    event_ids = excluded.event_ids
"""


def upsert_sessions_batch(
    session_updates: list[dict[str, Any] | Session],
    conn: sqlite3.Connection,
) -> None:
    """UPSERT a batch of session projections on the provided connection."""
    if not session_updates:
        return

    rows = [_format_session_row(s) for s in session_updates]
    conn.executemany(UPSERT_SESSION_SQL, rows)


def save_session(session: Any, conn: sqlite3.Connection | None = None) -> None:
    """Insert or update one session without replacing its original first_seen.

    Appends an authoritative snapshot of the session state to the append-only forensic ledger.
    Supports sharing a caller's transaction when conn is provided.
    """
    from .ledger import append_event

    manage_conn = conn is None
    target_conn = get_connection() if manage_conn else conn
    assert target_conn is not None

    data = _session_to_dict(session)
    row_tuple = _format_session_row(data)

    try:
        if manage_conn:
            target_conn.isolation_level = None
            target_conn.execute("BEGIN IMMEDIATE")

        target_conn.execute(UPSERT_SESSION_SQL, row_tuple)

        # Retrieve authoritative first_seen from database row
        saved_row = target_conn.execute(
            "SELECT first_seen FROM sessions WHERE session_id = ?",
            (data.get("session_id"),),
        ).fetchone()
        if saved_row and saved_row["first_seen"]:
            data["first_seen"] = saved_row["first_seen"]

        # Append authoritative snapshot to the forensic ledger on the SAME connection
        append_event("session_snapshot", data, conn=target_conn)

        if manage_conn:
            target_conn.execute("COMMIT")
    except Exception:
        if manage_conn:
            try:
                target_conn.execute("ROLLBACK")
            except sqlite3.Error:
                # Best-effort rollback: surface the original error, not this one.
                logger.warning("ROLLBACK failed after transaction error", exc_info=True)
        raise
    finally:
        if manage_conn:
            target_conn.close()


def save_session_snapshot(session: Any, conn: sqlite3.Connection | None = None) -> None:
    """Public helper matching kickoff specification to persist a session snapshot."""
    save_session(session, conn=conn)


def _session_from_row(row: sqlite3.Row) -> Session:
    keys = row.keys()
    reasons = _decode(row["reasons"] if "reasons" in keys else None, [])
    pages = _decode(row["pages"] if "pages" in keys else None, [])
    traps = _decode(row["traps_triggered"] if "traps_triggered" in keys else None, [])
    canaries = _decode(row["canaries_exposed"] if "canaries_exposed" in keys else None, [])
    event_ids = _decode(row["event_ids"] if "event_ids" in keys else None, [])

    client_ip = row["client_ip"] if "client_ip" in keys else (row["ip"] if "ip" in keys else "")

    return Session(
        session_id=str(row["session_id"]),
        client_key=str(row["client_key"] if "client_key" in keys else ""),
        client_ip=str(client_ip or ""),
        ip=str(client_ip or ""),
        asn=row["asn"] if "asn" in keys else None,
        asn_status=str(row["asn_status"] if "asn_status" in keys else "unavailable"),
        ja3_hash=str(row["ja3_hash"]) if "ja3_hash" in keys and row["ja3_hash"] else None,
        ja4_hash=str(row["ja4_hash"]) if "ja4_hash" in keys and row["ja4_hash"] else None,
        tls_source=str(row["tls_source"] if "tls_source" in keys else "none"),
        user_agent=str(row["user_agent"] if "user_agent" in keys else ""),
        header_fp=str(row["header_fp"] if "header_fp" in keys else ""),
        first_seen=str(row["first_seen"] if "first_seen" in keys else ""),
        last_seen=str(row["last_seen"] if "last_seen" in keys else ""),
        request_count=int(row["request_count"] if "request_count" in keys else 0),
        static_count=int(row["static_count"] if "static_count" in keys else 0),
        api_count=int(row["api_count"] if "api_count" in keys else 0),
        asset_ratio=float(row["asset_ratio"]) if "asset_ratio" in keys and row["asset_ratio"] is not None else None,
        trust_score=float(row["trust_score"]) if "trust_score" in keys and row["trust_score"] is not None else 0.0,
        ar_anomaly_streak=int(row["ar_anomaly_streak"]) if "ar_anomaly_streak" in keys and row["ar_anomaly_streak"] is not None else 0,
        locked_sandbox=bool(row["locked_sandbox"]) if "locked_sandbox" in keys and row["locked_sandbox"] is not None else False,
        state=str(row["state"] if "state" in keys else "SANDBOX"),
        classification=str(row["classification"] if "classification" in keys else "UNKNOWN"),
        decision=str(row["decision"] if "decision" in keys else "SANDBOX"),
        risk_score=int(row["risk_score"] if "risk_score" in keys else 0),
        reasons=reasons,
        pages=pages,
        traps_triggered=traps,
        canaries_exposed=canaries,
        event_ids=event_ids,
    )


def get_session(session_id: str, conn: sqlite3.Connection | None = None) -> Session | None:
    """Retrieve one session by session_id."""
    manage_conn = conn is None
    target_conn = get_connection() if manage_conn else conn
    assert target_conn is not None

    try:
        row = target_conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return _session_from_row(row) if row else None
    finally:
        if manage_conn:
            target_conn.close()


def list_sessions(
    classification: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[Session]:
    """List sessions ordered by last_seen descending, optionally filtered by classification."""
    manage_conn = conn is None
    target_conn = get_connection() if manage_conn else conn
    assert target_conn is not None

    try:
        if classification:
            rows = target_conn.execute(
                "SELECT * FROM sessions WHERE classification = ? ORDER BY last_seen DESC",
                (classification,),
            ).fetchall()
        else:
            rows = target_conn.execute(
                "SELECT * FROM sessions ORDER BY last_seen DESC"
            ).fetchall()
        return [_session_from_row(row) for row in rows]
    finally:
        if manage_conn:
            target_conn.close()
