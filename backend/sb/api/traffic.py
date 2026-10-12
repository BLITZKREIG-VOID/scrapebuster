from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..contracts import TrafficEvent, TrafficEvents
from ..store.db import get_connection

logger = logging.getLogger("sb.api.traffic")

router = APIRouter()


def _row_to_event(row: dict) -> TrafficEvent:
    # reasons
    reasons_raw = row.get("reasons")
    if isinstance(reasons_raw, str):
        try:
            reasons = json.loads(reasons_raw)
        except (ValueError, TypeError):
            reasons = []
    elif isinstance(reasons_raw, list):
        reasons = reasons_raw
    else:
        reasons = []

    # header_order
    ho_raw = row.get("header_order")
    if isinstance(ho_raw, str):
        try:
            header_order = json.loads(ho_raw)
        except (ValueError, TypeError):
            header_order = []
    elif isinstance(ho_raw, list):
        header_order = ho_raw
    else:
        header_order = []

    # canary_ids
    canary_raw = row.get("canary_ids")
    if isinstance(canary_raw, str):
        try:
            canary_ids = json.loads(canary_raw)
        except (ValueError, TypeError):
            canary_ids = []
    elif isinstance(canary_raw, list):
        canary_ids = canary_raw
    else:
        canary_ids = []

    client_ip = row.get("client_ip") or row.get("ip") or ""
    asn_val = row.get("asn")
    if asn_val is not None:
        try:
            asn_val = int(asn_val)
        except (ValueError, TypeError):
            asn_val = None

    return TrafficEvent(
        seq=row["seq"],
        event_id=row["event_id"],
        ts=row["ts"],
        session_id=row["session_id"],
        client_key=row.get("client_key") or "",
        client_ip=client_ip,
        ip=client_ip,
        asn=asn_val,
        asn_status=row.get("asn_status") or "unavailable",
        ja3_hash=row.get("ja3_hash"),
        ja4_hash=row.get("ja4_hash"),
        http_version=row.get("http_version") or "HTTP/1.1",
        header_order=header_order,
        header_fp=row.get("header_fp") or "",
        tls_source=row.get("tls_source") or "none",
        method=row["method"],
        path=row["path"],
        status_code=row["status_code"],
        user_agent=row.get("user_agent") or "",
        stage=row.get("stage"),
        layer=row.get("layer") or "ORIGIN",
        decision="SANDBOX",
        risk_score=row.get("risk_score") or 0,
        reasons=reasons,
        canary_ids=canary_ids,
    )


def _fetch_events(cursor: int, limit: int, session_id: str | None = None) -> tuple[list[TrafficEvent], int]:
    conn = get_connection()
    try:
        cursor_obj = conn.cursor()
        if session_id:
            cursor_obj.execute(
                "SELECT * FROM traffic_events WHERE seq > ? AND session_id = ? ORDER BY seq ASC LIMIT ?",
                (cursor, session_id, limit),
            )
        else:
            cursor_obj.execute(
                "SELECT * FROM traffic_events WHERE seq > ? ORDER BY seq ASC LIMIT ?",
                (cursor, limit),
            )
        rows = cursor_obj.fetchall()
        events = []
        last_seq = cursor
        for r in rows:
            event = _row_to_event(dict(r))
            events.append(event)
            last_seq = event.seq
        return events, last_seq
    finally:
        conn.close()


@router.get("/traffic/events", response_model=TrafficEvents)
async def get_traffic_events(
    after: int = Query(0, ge=0, description="Sequence number to fetch after"),
    since_seq: int | None = Query(None, ge=0, description="Alternative cursor parameter"),
    limit: int = Query(200, ge=1, le=1000, description="Max events to return"),
    session_id: str | None = Query(None, description="Filter by session ID"),
) -> TrafficEvents:
    curr_since = since_seq if isinstance(since_seq, int) else None
    curr_after = after if isinstance(after, int) else 0
    curr_cursor = curr_since if curr_since is not None else curr_after
    curr_limit = limit if isinstance(limit, int) else 200
    curr_sid = session_id if isinstance(session_id, str) else None

    try:
        from ..edge.telemetry import TelemetryTap

        await TelemetryTap.flush()
    except (sqlite3.Error, OSError, RuntimeError, ImportError):
        logger.debug("TelemetryTap flush skipped", exc_info=True)

    events, last_seq = _fetch_events(curr_cursor, curr_limit, curr_sid)
    return TrafficEvents(events=events, last_seq=last_seq)


@router.get("/traffic", response_model=TrafficEvents)
async def get_traffic(
    after: int = Query(0, ge=0, description="Sequence number to fetch after"),
    since_seq: int | None = Query(None, ge=0, description="Alternative cursor parameter"),
    limit: int = Query(200, ge=1, le=1000, description="Max events to return"),
    session_id: str | None = Query(None, description="Filter by session ID"),
) -> TrafficEvents:
    curr_since = since_seq if isinstance(since_seq, int) else None
    curr_after = after if isinstance(after, int) else 0
    curr_cursor = curr_since if curr_since is not None else curr_after
    curr_limit = limit if isinstance(limit, int) else 200
    curr_sid = session_id if isinstance(session_id, str) else None

    try:
        from ..edge.telemetry import TelemetryTap

        await TelemetryTap.flush()
    except (sqlite3.Error, OSError, RuntimeError, ImportError):
        logger.debug("TelemetryTap flush skipped", exc_info=True)

    events, last_seq = _fetch_events(curr_cursor, curr_limit, curr_sid)
    return TrafficEvents(events=events, last_seq=last_seq)


@router.get("/traffic/stream")
async def stream_traffic(
    since_seq: int = Query(0, ge=0, description="Starting sequence number"),
):
    async def event_generator() -> AsyncGenerator[str, None]:
        current_seq = since_seq
        while True:
            events, new_seq = _fetch_events(current_seq, 50)
            if events:
                for ev in events:
                    yield f"data: {json.dumps(ev.model_dump())}\n\n"
                current_seq = new_seq
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
