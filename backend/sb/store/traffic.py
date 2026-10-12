"""Store traffic events persistence and cursor-based querying for ScrapeBuster Phase 1."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from .db import get_connection
from .models import TrafficEventRecord

logger = logging.getLogger("sb.store.traffic")


def _json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))


def _decode_json(value: Any, default: Any) -> Any:
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _format_event_row(event: dict[str, Any] | TrafficEventRecord) -> tuple:
    data = event.to_dict() if hasattr(event, "to_dict") else dict(event)

    event_id = str(data.get("event_id") or f"evt-{uuid.uuid4().hex}")
    ts = str(data.get("ts") or datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    session_id = str(data.get("session_id") or "unknown")
    client_key = str(data.get("client_key") or "")
    client_ip = str(data.get("client_ip") or data.get("ip") or "127.0.0.1")
    ip = client_ip

    asn_val = data.get("asn")
    if asn_val is not None:
        try:
            asn_int = int(asn_val)
        except (ValueError, TypeError):
            asn_int = None
    else:
        asn_int = None

    asn_status = str(data.get("asn_status") or ("loopback" if client_ip in ("127.0.0.1", "::1") else "unavailable"))
    ja3_hash = str(data.get("ja3_hash")) if data.get("ja3_hash") else None
    ja4_hash = str(data.get("ja4_hash")) if data.get("ja4_hash") else None
    tls_source = str(data.get("tls_source") or "none")
    http_version = str(data.get("http_version") or "HTTP/1.1")
    header_order = _json(data.get("header_order") or [])
    header_fp = str(data.get("header_fp") or "")
    method = str(data.get("method") or "GET")
    path = str(data.get("path") or "/")
    status_code = int(data.get("status_code") or 200)
    user_agent = str(data.get("user_agent") or "")
    stage = str(data.get("stage") or "offense")
    layer = str(data.get("layer") or "ORIGIN")
    decision = str(data.get("decision") or "SANDBOX")
    risk_score = int(data.get("risk_score") or 0)
    reasons = _json(data.get("reasons") or [])
    canary_ids = _json(data.get("canary_ids") or [])
    route_class = str(data.get("route_class") or "unknown")

    return (
        event_id,
        ts,
        session_id,
        client_key,
        client_ip,
        ip,
        asn_int,
        asn_status,
        ja3_hash,
        ja4_hash,
        tls_source,
        http_version,
        header_order,
        header_fp,
        method,
        path,
        status_code,
        user_agent,
        stage,
        layer,
        decision,
        risk_score,
        reasons,
        canary_ids,
        route_class,
    )


def insert_traffic_events_batch(
    events: list[dict[str, Any] | TrafficEventRecord],
    conn: sqlite3.Connection,
) -> None:
    """Insert a batch of traffic events into the operational traffic_events projection.

    Must be executed within an active transaction on the provided connection.
    """
    if not events:
        return

    rows = [_format_event_row(evt) for evt in events]
    conn.executemany(
        """
        INSERT INTO traffic_events (
            event_id, ts, session_id, client_key, client_ip, ip,
            asn, asn_status, ja3_hash, ja4_hash, tls_source, http_version,
            header_order, header_fp, method, path, status_code, user_agent,
            stage, layer, decision, risk_score, reasons, canary_ids, route_class
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def save_traffic_event(
    event: dict[str, Any] | TrafficEventRecord,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Save a single traffic event to the traffic_events table and append to forensic ledger."""
    from .ledger import append_event

    manage_conn = conn is None
    target_conn = get_connection() if manage_conn else conn
    assert target_conn is not None

    data = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    row_tuple = _format_event_row(data)

    try:
        if manage_conn:
            target_conn.isolation_level = None
            target_conn.execute("BEGIN IMMEDIATE")

        target_conn.execute(
            """
            INSERT INTO traffic_events (
                event_id, ts, session_id, client_key, client_ip, ip,
                asn, asn_status, ja3_hash, ja4_hash, tls_source, http_version,
                header_order, header_fp, method, path, status_code, user_agent,
                stage, layer, decision, risk_score, reasons, canary_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row_tuple,
        )

        append_event("traffic", data, conn=target_conn)

        if manage_conn:
            target_conn.execute("COMMIT")

        return data
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


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    keys = row.keys()
    client_ip = row["client_ip"] if "client_ip" in keys else (row["ip"] if "ip" in keys else "")
    return {
        "seq": int(row["seq"]) if "seq" in keys else None,
        "event_id": str(row["event_id"]),
        "ts": str(row["ts"]),
        "session_id": str(row["session_id"]),
        "client_key": str(row["client_key"] if "client_key" in keys else ""),
        "client_ip": str(client_ip or ""),
        "ip": str(client_ip or ""),
        "asn": row["asn"] if "asn" in keys else None,
        "asn_status": str(row["asn_status"] if "asn_status" in keys else "unavailable"),
        "ja3_hash": row["ja3_hash"] if "ja3_hash" in keys else None,
        "ja4_hash": row["ja4_hash"] if "ja4_hash" in keys else None,
        "tls_source": str(row["tls_source"] if "tls_source" in keys else "none"),
        "http_version": str(row["http_version"] if "http_version" in keys else "HTTP/1.1"),
        "header_order": _decode_json(row["header_order"] if "header_order" in keys else None, []),
        "header_fp": str(row["header_fp"] if "header_fp" in keys else ""),
        "method": str(row["method"] if "method" in keys else "GET"),
        "path": str(row["path"] if "path" in keys else "/"),
        "status_code": int(row["status_code"] if "status_code" in keys else 200),
        "user_agent": str(row["user_agent"] if "user_agent" in keys else ""),
        "stage": str(row["stage"] if "stage" in keys else "offense"),
        "layer": str(row["layer"] if "layer" in keys else "ORIGIN"),
        "decision": str(row["decision"] if "decision" in keys else "SANDBOX"),
        "risk_score": int(row["risk_score"] if "risk_score" in keys else 0),
        "reasons": _decode_json(row["reasons"] if "reasons" in keys else None, []),
        "canary_ids": _decode_json(row["canary_ids"] if "canary_ids" in keys else None, []),
        "route_class": str(row["route_class"] if "route_class" in keys else "unknown"),
    }


def get_traffic_events(
    after_seq: int = 0,
    limit: int = 100,
    conn: sqlite3.Connection | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Cursor-based traffic event pagination by sequence number (seq > after_seq).

    Returns (events, last_seq).
    """
    manage_conn = conn is None
    target_conn = get_connection() if manage_conn else conn
    assert target_conn is not None

    try:
        cursor = target_conn.cursor()
        cursor.execute(
            "SELECT * FROM traffic_events WHERE seq > ? ORDER BY seq ASC LIMIT ?",
            (int(after_seq), int(limit)),
        )
        rows = cursor.fetchall()
        events = [_row_to_dict(r) for r in rows]
        last_seq = events[-1]["seq"] if events and events[-1]["seq"] is not None else after_seq
        return events, last_seq
    finally:
        if manage_conn:
            target_conn.close()


def get_traffic_event(
    event_id: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """Fetch single traffic event by event_id."""
    manage_conn = conn is None
    target_conn = get_connection() if manage_conn else conn
    assert target_conn is not None

    try:
        row = target_conn.execute(
            "SELECT * FROM traffic_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        if manage_conn:
            target_conn.close()


def count_traffic_events(conn: sqlite3.Connection | None = None) -> int:
    """Return total count of traffic events in projection table."""
    manage_conn = conn is None
    target_conn = get_connection() if manage_conn else conn
    assert target_conn is not None

    try:
        row = target_conn.execute("SELECT count(*) FROM traffic_events").fetchone()
        return int(row[0]) if row else 0
    finally:
        if manage_conn:
            target_conn.close()


def get_decision_counts(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """Return aggregated counts by decision (FAST_PATH, SANDBOX)."""
    manage_conn = conn is None
    target_conn = get_connection() if manage_conn else conn
    assert target_conn is not None

    try:
        rows = target_conn.execute(
            "SELECT decision, COUNT(*) AS count FROM traffic_events GROUP BY decision"
        ).fetchall()
        counts: dict[str, int] = {"FAST_PATH": 0, "SANDBOX": 0}
        for r in rows:
            dec = str(r["decision"])
            cnt = int(r["count"])
            counts[dec] = cnt
        return counts
    finally:
        if manage_conn:
            target_conn.close()
