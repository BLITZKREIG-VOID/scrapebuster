"""Layer 3 trap classification and hit persistence."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import secrets
from typing import Any

from sb.canary import registry
from sb.store import db
from sb.trap.honeypots import (
    DECOY_API_PATH,
    HIDDEN_LINK_PATH,
    L2_BAND,
    ROBOTS_PREFIX,
)


@dataclass(frozen=True)
class TrapHit:
    trap_id: str
    trap_type: str
    path: str


def match_trap(path: str | None, session: Any = None) -> TrapHit | None:
    """Pure trap matcher.

    Rules:
    - DECOY_API_PATH -> TRAP-DECOY-01 (most specific first)
    - path == "/internal" or startswith ROBOTS_PREFIX -> TRAP-ROBOTS-01
    - HIDDEN_LINK_PATH -> TRAP-LINK-01
    - else if session is given, state != "TRAPPED" and L2_BAND[0] <= l2_score <= L2_BAND[1] -> TRAP-BAND-L2
    - else None.

    Path matching ignores trailing slashes except for the "/internal/" prefix rule.
    """
    if path is None:
        path = ""

    p_norm = path.rstrip("/") if path != "/" else "/"
    decoy_norm = DECOY_API_PATH.rstrip("/")
    hidden_link_norm = HIDDEN_LINK_PATH.rstrip("/")

    if p_norm == decoy_norm:
        return TrapHit(trap_id="TRAP-DECOY-01", trap_type="decoy_api", path=path)

    if path == "/internal" or path.startswith(ROBOTS_PREFIX):
        return TrapHit(trap_id="TRAP-ROBOTS-01", trap_type="robots_disallowed", path=path)

    if p_norm == hidden_link_norm:
        return TrapHit(trap_id="TRAP-LINK-01", trap_type="hidden_link", path=path)

    if session is not None:
        state = getattr(session, "state", None)
        l2_score = getattr(session, "l2_score", 0)
        if state != "TRAPPED" and L2_BAND[0] <= l2_score <= L2_BAND[1]:
            return TrapHit(trap_id="TRAP-BAND-L2", trap_type="l2_band", path=path)

    return None


def classify_request(ctx: Any, session: Any = None) -> TrapHit | None:
    """Classify request path and session against traps, recording hit when matched."""
    path = getattr(ctx, "path", "")
    hit = match_trap(path, session)
    if hit is not None:
        hit_id = f"HIT-{secrets.token_hex(4)}"
        ts = registry.now_iso()
        session_id = getattr(session, "session_id", None)
        session_id_str = str(session_id) if session_id is not None else ""
        with closing(db.get_connection()) as conn, conn:
            conn.execute(
                """
                INSERT INTO trap_hits (hit_id, ts, session_id, trap_id, trap_type, path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (hit_id, ts, session_id_str, hit.trap_id, hit.trap_type, hit.path),
            )
    return hit


def list_trap_hits(session_id: str | None = None) -> list[dict]:
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
