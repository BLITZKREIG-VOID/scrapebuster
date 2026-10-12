"""Offense path classification and trap hit persistence for ScrapeBuster Phase 1."""

from __future__ import annotations

import logging
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any

from sb.canary import registry
from sb.config import is_segment_match
from sb.offense.honeypots import (
    get_configured_trap_api_path,
    get_configured_trap_paths,
)
from sb.store import db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrapHit:
    trap_id: str
    trap_type: str
    path: str


def match_trap(path: str | None, session: Any = None) -> TrapHit | None:
    """Match request path against configured trap paths and decoy API paths.

    Uses configured paths only; does not claim customer origin paths by default.
    Segment-safe: matches exact path or subpath under boundary (including API descendants).
    """
    if not path:
        return None

    api_path = get_configured_trap_api_path()
    if api_path and is_segment_match(path, api_path):
        return TrapHit(trap_id="TRAP-DECOY-01", trap_type="decoy_api", path=path)

    trap_paths = get_configured_trap_paths()
    if trap_paths:
        for tp in trap_paths:
            if is_segment_match(path, tp):
                return TrapHit(trap_id="TRAP-PATH-01", trap_type="trap_path", path=path)

    return None


def classify_request(
    ctx: Any,
    session: Any = None,
    conn: sqlite3.Connection | None = None,
) -> TrapHit | None:
    """Classify request path against configured traps, persisting hit to DB and forensic ledger."""
    path = getattr(ctx, "path", "") or ""
    hit = match_trap(path, session)
    if hit is not None:
        hit_id = f"HIT-{secrets.token_hex(16)}"
        ts = registry.now_iso()
        session_id = getattr(session, "session_id", None)
        session_id_str = str(session_id) if session_id is not None else ""

        # Note trap in session in-memory state
        if (
            session is not None
            and hasattr(session, "traps_triggered")
            and isinstance(session.traps_triggered, list)
        ):
            if path and path not in session.traps_triggered:
                session.traps_triggered.append(path)

        manage_conn = conn is None
        target_conn = db.get_connection() if manage_conn else conn
        assert target_conn is not None
        try:
            target_conn.execute(
                """
                INSERT INTO trap_hits (hit_id, ts, session_id, trap_id, trap_type, path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (hit_id, ts, session_id_str, hit.trap_id, hit.trap_type, hit.path),
            )
            if manage_conn:
                target_conn.commit()
        except Exception as exc:
            logger.error("Failed to insert trap_hit to DB: %s", exc)
            raise
        finally:
            if manage_conn:
                target_conn.close()

        # Persist chained trap_hit event to forensic ledger
        from sb.store.ledger import append_event

        append_event(
            "trap_hit",
            {
                "hit_id": hit_id,
                "ts": ts,
                "session_id": session_id_str,
                "trap_id": hit.trap_id,
                "trap_type": hit.trap_type,
                "path": hit.path,
            },
            conn=conn,
        )

    return hit


def list_trap_hits(
    session_id: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """List recorded trap hits, optionally filtered by session_id, ordered by ts ascending."""
    manage_conn = conn is None
    target_conn = db.get_connection() if manage_conn else conn
    assert target_conn is not None
    try:
        if session_id is not None:
            rows = target_conn.execute(
                "SELECT * FROM trap_hits WHERE session_id = ? ORDER BY ts ASC",
                (str(session_id),),
            ).fetchall()
        else:
            rows = target_conn.execute(
                "SELECT * FROM trap_hits ORDER BY ts ASC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if manage_conn:
            target_conn.close()
