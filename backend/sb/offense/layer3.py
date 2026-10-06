"""Offense path classification and trap hit persistence."""

from __future__ import annotations

import secrets
from contextlib import closing
from dataclasses import dataclass
from typing import Any

from sb.canary import registry
from sb.offense.honeypots import (
    get_configured_trap_api_path,
    get_configured_trap_paths,
)
from sb.store import db


@dataclass(frozen=True)
class TrapHit:
    trap_id: str
    trap_type: str
    path: str


def match_trap(path: str | None, session: Any = None) -> TrapHit | None:
    """Match request path against configured trap paths and decoy API paths.

    Uses configured paths only; does not claim customer origin paths by default.
    """
    if not path:
        return None

    api_path = get_configured_trap_api_path()
    if api_path:
        norm_path = path.rstrip("/") if path != "/" else "/"
        norm_api = api_path.rstrip("/") if api_path != "/" else "/"
        if norm_path == norm_api:
            return TrapHit(trap_id="TRAP-DECOY-01", trap_type="decoy_api", path=path)

    trap_paths = get_configured_trap_paths()
    if trap_paths:
        norm_path = path.rstrip("/") if path != "/" else "/"
        for tp in trap_paths:
            norm_tp = tp.rstrip("/") if tp != "/" else "/"
            if norm_path == norm_tp or path.startswith(tp if tp.endswith("/") else tp + "/"):
                return TrapHit(trap_id="TRAP-PATH-01", trap_type="trap_path", path=path)

    return None


def classify_request(ctx: Any, session: Any = None) -> TrapHit | None:
    """Classify request path against configured traps, recording hit when matched."""
    path = getattr(ctx, "path", "")
    hit = match_trap(path, session)
    if hit is not None:
        hit_id = f"HIT-{secrets.token_hex(4)}"
        ts = registry.now_iso()
        session_id = getattr(session, "session_id", None)
        session_id_str = str(session_id) if session_id is not None else ""
        try:
            with closing(db.get_connection()) as conn, conn:
                conn.execute(
                    """
                    INSERT INTO trap_hits (hit_id, ts, session_id, trap_id, trap_type, path)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (hit_id, ts, session_id_str, hit.trap_id, hit.trap_type, hit.path),
                )
        except Exception:
            pass
    return hit


def list_trap_hits(session_id: str | None = None) -> list[dict[str, Any]]:
    """List recorded trap hits, optionally filtered by session_id, ordered by ts ascending."""
    with closing(db.get_connection()) as conn, conn:
        if session_id is not None:
            rows = conn.execute(
                "SELECT * FROM trap_hits WHERE session_id = ? ORDER BY ts ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trap_hits ORDER BY ts ASC"
            ).fetchall()
        return [dict(r) for r in rows]
