"""Callback Engine for ScrapeBuster Phase 4 (PRD M4 / FR-4.1, FR-4.2).

Implements:
- Image callback endpoint returning 1×1 pixel with session/canary correlation
- Honey-key interception endpoint capturing exfiltration attempts
- Request metadata capture with canary-to-session correlation
- Callback routes exempt from mutation
- Persistent, chained callback events in forensic ledger
"""

from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import threading
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sb.canary import registry
from sb.store import db
from sb.store.ledger import append_event

logger = logging.getLogger("sb.callbacks")

# ---------------------------------------------------------------------------
# Callback Router (mounted at /api/v1/callbacks)
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/callbacks", tags=["callbacks"])

# Thread-local connection cache
_conn_local = threading.local()


def get_callback_conn() -> sqlite3.Connection:
    if not hasattr(_conn_local, "conn") or _conn_local.conn is None:
        _conn_local.conn = db.get_connection()
    return _conn_local.conn


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ImageCallbackRequest(BaseModel):
    """Query parameters for image callback."""
    c: str = Field(..., description="Canary ID (SB-CANARY-<session_hash>-<seq>)")
    t: str | None = Field(None, description="Optional token value for verification")
    s: str | None = Field(None, description="Optional session ID for explicit correlation")


class HoneyKeySubmitRequest(BaseModel):
    """Request body for honey-key interception."""
    key_id: str = Field(..., description="Honey key identifier")
    key_value: str = Field(..., description="Honey key value that was exfiltrated")
    source_url: str | None = Field(None, description="URL where key was found")
    session_id: str | None = Field(None, description="Associated session ID if known")


class CallbackEventResponse(BaseModel):
    callback_id: str
    status: str
    canary_id: str | None = None
    session_id: str | None = None
    ts: str


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _generate_callback_id() -> str:
    """Generate unique callback ID."""
    return f"CBK-{secrets.token_hex(4)}"


def _extract_request_metadata(request: Request) -> dict[str, Any]:
    """Extract full request metadata for forensic correlation."""
    client_ip = getattr(getattr(request, "client", None), "host", "unknown") or "unknown"
    headers = {k.lower(): v for k, v in request.headers.items()}
    return {
        "ip": client_ip,
        "user_agent": headers.get("user-agent", ""),
        "referer": headers.get("referer", ""),
        "accept_language": headers.get("accept-language", ""),
        "headers": headers,
        "method": request.method,
        "path": str(request.url.path),
        "query_params": dict(request.query_params),
    }


def _resolve_session_from_canary(canary_id: str) -> tuple[str, str] | None:
    """Resolve session ID from canary ID via registry binding.
    
    Returns (session_id, binding_value) or None if not found.
    """
    try:
        binding = registry.get_session_binding(canary_id)
        if binding:
            return binding.session_id, binding.value
    except (sqlite3.Error, KeyError, ValueError, AttributeError) as exc:
        logger.warning("Failed to resolve session for canary %s: %s", canary_id, exc)
    return None


def _append_callback_event(
    kind: str,
    record: dict[str, Any],
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Append callback event to forensic ledger with chaining."""
    return append_event(kind, record, conn=conn)


# ---------------------------------------------------------------------------
# Image Callback Endpoint (1×1 pixel)
# ---------------------------------------------------------------------------

@router.get("/image.gif", response_class=Response)
@router.get("/beacon.gif", response_class=Response)
async def image_callback(
    request: Request,
    c: str | None = Query(None, description="Canary ID"),
    t: str | None = Query(None, description="Optional token"),
    s: str | None = Query(None, description="Optional session ID"),
    c_header: str | None = Header(None, alias="c"),
    t_header: str | None = Header(None, alias="t"),
    s_header: str | None = Header(None, alias="s"),
) -> Response:
    """Image callback endpoint returning 1x1 transparent GIF.
    
    Correlates canary ID to session via registry binding.
    Exempt from mutation pipeline.
    Persists callback event to forensic ledger.
    """
    canary_id = c or c_header
    token_val = t or t_header
    session_id = s or s_header
    if not canary_id:
        raise HTTPException(status_code=400, detail="Missing required canary parameter 'c'")

    callback_id = f"CBK-{secrets.token_hex(4)}"
    ts = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    metadata = _extract_request_metadata(request)

    # Resolve session from canary ID
    binding_value = None
    if canary_id and not session_id:
        resolved = _resolve_session_from_canary(canary_id)
        if resolved:
            session_id, binding_value = resolved

    # Verify token if provided
    token_verified = False
    if token_val and binding_value and token_val == binding_value:
        token_verified = True

    # Persist callback event
    callback_record = {
        "callback_id": callback_id,
        "canary_id": canary_id,
        "session_id": session_id,
        "token_verified": token_verified,
        "binding_value": binding_value,
        "metadata": metadata,
        "ts": ts,
    }

    try:
        from sb.store.ledger import append_event
        append_event("image_callback", callback_record)
    except (ImportError, sqlite3.Error, OSError, ValueError, TypeError) as exc:
        logger.error("Failed to persist image callback event: %s", exc)

    # Return 1x1 transparent GIF
    transparent_gif = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
        b"\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00"
        b"\x00\x00\x01\x00\x01\x00\x00\x02\x01D\x00;"
    )

    return Response(
        content=transparent_gif,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, private, max-age=0",
            "X-Callback-ID": callback_id,
        },
    )


# ---------------------------------------------------------------------------
# Honey-Key Interception Endpoint
# ---------------------------------------------------------------------------
# Honey-Key Interception Endpoint
# ---------------------------------------------------------------------------

@router.post("/honeykey", response_model=CallbackEventResponse)
async def honeykey_interception(
    request: Request,
    payload: HoneyKeySubmitRequest,
) -> CallbackEventResponse:
    """Honey-key interception endpoint.
    
    Captures exfiltration attempts of synthetic API keys/secrets.
    Correlates key to session via registry binding.
    Persists event to forensic ledger.
    """
    callback_id = f"CBK-{secrets.token_hex(4)}"
    ts = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    metadata = _extract_request_metadata(request)

    # Resolve session from key_id if it's a canary ID
    session_id = payload.session_id
    if payload.key_id and not session_id:
        resolved = _resolve_session_from_canary(payload.key_id)
        if resolved:
            session_id = resolved[0]

    # Persist honey-key event
    honeykey_record = {
        "callback_id": callback_id,
        "key_id": payload.key_id,
        "key_value": payload.key_value,
        "source_url": payload.source_url,
        "session_id": session_id,
        "metadata": metadata,
        "ts": ts,
    }

    try:
        from sb.store.ledger import append_event
        append_event("honeykey_interception", honeykey_record)
    except (ImportError, sqlite3.Error, OSError, ValueError, TypeError) as exc:
        logger.error("Failed to persist honeykey event: %s", exc)

    # Also append to evidence ledger as honeykey_exposed event
    try:
        from sb.store.ledger import append_event
        append_event("honeykey_exposed", {
            "event_id": f"HKE-{secrets.token_hex(4)}",
            "key_id": payload.key_id,
            "session_id": session_id,
            "source_ip": metadata["ip"],
            "user_agent": metadata["user_agent"],
            "source_url": payload.source_url,
            "ts": ts,
        })
    except (ImportError, sqlite3.Error, OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to append honeykey_exposed to ledger: %s", exc)

    return CallbackEventResponse(
        callback_id=f"CBK-{secrets.token_hex(4)}",
        status="captured",
        canary_id=payload.key_id,
        session_id=session_id,
        ts=ts,
    )


# ---------------------------------------------------------------------------
# Callback Query API
# ---------------------------------------------------------------------------

@router.get("/events", response_model=list[CallbackEventResponse])
async def list_callback_events(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session_id: str | None = None,
    canary_id: str | None = None,
) -> list[CallbackEventResponse]:
    """List callback events from forensic ledger."""
    from sb.store import db
    conn = db.get_connection()
    try:
        query = "SELECT * FROM forensic_ledger WHERE kind IN ('image_callback', 'honeykey_interception')"
        params: list[Any] = []
        
        if session_id:
            query += " AND json_extract(record, '$.session_id') = ?"
            params.append(session_id)
        if canary_id:
            query += " AND json_extract(record, '$.canary_id') = ?"
            params.append(canary_id)
        
        query += " ORDER BY seq DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        rows = conn.execute(query, params).fetchall()
        
        events = []
        for row in rows:
            record = json.loads(row["record"])
            events.append(CallbackEventResponse(
                callback_id=record.get("callback_id", ""),
                status=record.get("status", "captured"),
                canary_id=record.get("canary_id"),
                session_id=record.get("session_id"),
                ts=record.get("ts", ""),
            ))
        return events
    finally:
        conn.close()


@router.get("/events/{callback_id}", response_model=CallbackEventResponse)
async def get_callback_event(callback_id: str) -> CallbackEventResponse:
    """Get specific callback event by ID."""
    from sb.store import db
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM forensic_ledger WHERE json_extract(record, '$.callback_id') = ? ORDER BY seq DESC LIMIT 1",
            (callback_id,),
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Callback event not found")
        
        record = json.loads(row["record"])
        return CallbackEventResponse(
            callback_id=record.get("callback_id", ""),
            status=record.get("status", "captured"),
            canary_id=record.get("canary_id"),
            session_id=record.get("session_id"),
            ts=record.get("ts", ""),
        )
    finally:
        conn.close()