"""Canary registry: persistence, status transitions, publications, exposures."""

from __future__ import annotations

import json
import secrets
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from sb.canary import hashing
from sb.contracts import Canary, ExposureEvent
from sb.store import db

CANARIES_YAML: Path = Path(__file__).resolve().parent / "canaries.yaml"


class InvalidTransition(ValueError):
    """Raised when an invalid status transition is attempted on a canary."""


def now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format with microsecond precision and Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def load_definitions(path: Path | None = None) -> list[dict]:
    """Load raw canary definitions from YAML."""
    p = path or CANARIES_YAML
    content = p.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    if isinstance(data, dict) and "canaries" in data:
        return data["canaries"]
    if isinstance(data, list):
        return data
    return []


def _row_to_canary(row: sqlite3.Row | dict) -> Canary:
    d = dict(row)
    for field in ("context_terms", "probe_prompts", "placements"):
        val = d.get(field)
        if isinstance(val, str):
            d[field] = json.loads(val)
        elif val is None:
            d[field] = []
    return Canary.model_validate(d)


def _row_to_publication(row: sqlite3.Row | dict) -> dict:
    d = dict(row)
    val = d.get("placements")
    if isinstance(val, str):
        try:
            d["placements"] = json.loads(val)
        except Exception:
            pass
    elif val is None:
        d["placements"] = []
    return d


def _row_to_exposure(row: sqlite3.Row | dict) -> ExposureEvent:
    d = dict(row)
    for field in ("client", "request"):
        val = d.get(field)
        if isinstance(val, str):
            d[field] = json.loads(val)
        elif val is None:
            d[field] = {}
    return ExposureEvent.model_validate(d)


def upsert_canary(record: dict | Canary) -> Canary:
    """Upsert a canary record into the canaries table.

    `record` has Canary fields (including canonical_content, not content).
    """
    if isinstance(record, Canary):
        data = record.model_dump()
    else:
        data = dict(record)

    canary_id = data["canary_id"]
    canary_type = data["type"]
    canonical_content = data["canonical_content"]
    anchor = data["anchor"]
    context_terms = data.get("context_terms", [])
    probe_prompts = data.get("probe_prompts", [])
    sha256 = data["sha256"]
    content_version = data["content_version"]
    created_at = data.get("created_at") or now_iso()
    published_at = data.get("published_at")
    status = data.get("status", "DRAFT")
    placements = data.get("placements", [])

    context_terms_json = json.dumps(context_terms) if not isinstance(context_terms, str) else context_terms
    probe_prompts_json = json.dumps(probe_prompts) if not isinstance(probe_prompts, str) else probe_prompts
    placements_json = json.dumps(placements) if not isinstance(placements, str) else placements

    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            """
            INSERT INTO canaries (
                canary_id, type, canonical_content, anchor, context_terms,
                probe_prompts, sha256, content_version, created_at, published_at,
                status, placements
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canary_id) DO UPDATE SET
                type = excluded.type,
                canonical_content = excluded.canonical_content,
                anchor = excluded.anchor,
                context_terms = excluded.context_terms,
                probe_prompts = excluded.probe_prompts,
                sha256 = excluded.sha256,
                content_version = excluded.content_version,
                created_at = excluded.created_at,
                published_at = excluded.published_at,
                status = excluded.status,
                placements = excluded.placements
            """,
            (
                canary_id,
                canary_type,
                canonical_content,
                anchor,
                context_terms_json,
                probe_prompts_json,
                sha256,
                content_version,
                created_at,
                published_at,
                status,
                placements_json,
            ),
        )
        row = conn.execute("SELECT * FROM canaries WHERE canary_id = ?", (canary_id,)).fetchone()
        return _row_to_canary(row)


def get(canary_id: str) -> Canary | None:
    """Retrieve a canary by its ID, or None if not found."""
    with closing(db.get_connection()) as conn, conn:
        row = conn.execute("SELECT * FROM canaries WHERE canary_id = ?", (canary_id,)).fetchone()
        if row is None:
            return None
        return _row_to_canary(row)


def list_canaries() -> list[Canary]:
    """List all canaries ordered by canary_id."""
    with closing(db.get_connection()) as conn, conn:
        rows = conn.execute("SELECT * FROM canaries ORDER BY canary_id ASC").fetchall()
        return [_row_to_canary(r) for r in rows]


def record_publication(canary_id: str, published_at: str) -> dict:
    """Upsert publications row from the canary row and set canaries.published_at."""
    with closing(db.get_connection()) as conn, conn:
        row = conn.execute(
            "SELECT sha256, content_version, placements FROM canaries WHERE canary_id = ?",
            (canary_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Canary {canary_id} not found")

        sha256 = row["sha256"]
        content_version = row["content_version"]
        placements_raw = row["placements"]

        if isinstance(placements_raw, str):
            placements_text = placements_raw
            placements_obj = json.loads(placements_raw)
        else:
            placements_text = json.dumps(placements_raw)
            placements_obj = placements_raw

        conn.execute(
            """
            INSERT INTO publications (canary_id, sha256, content_version, published_at, placements)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(canary_id) DO UPDATE SET
                sha256 = excluded.sha256,
                content_version = excluded.content_version,
                published_at = excluded.published_at,
                placements = excluded.placements
            """,
            (canary_id, sha256, content_version, published_at, placements_text),
        )
        conn.execute(
            "UPDATE canaries SET published_at = ? WHERE canary_id = ?",
            (published_at, canary_id),
        )
        return {
            "canary_id": canary_id,
            "sha256": sha256,
            "content_version": content_version,
            "published_at": published_at,
            "placements": placements_obj,
        }


def get_publication(canary_id: str) -> dict | None:
    """Retrieve a publication record by canary_id, or None if not found."""
    with closing(db.get_connection()) as conn, conn:
        row = conn.execute("SELECT * FROM publications WHERE canary_id = ?", (canary_id,)).fetchone()
        if row is None:
            return None
        return _row_to_publication(row)


def _extract(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    val = obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)
    if val is None and hasattr(obj, "request"):
        req = getattr(obj, "request", None)
        if req is not None:
            val = req.get(key) if isinstance(req, Mapping) else getattr(req, key, None)
    return val



def record_exposure(
    canary_id: str,
    session: Any,
    ctx: Any,
    resource: str,
    block_text: str,
    ts: str | None = None,
) -> ExposureEvent:
    """Record an exposure event and transition canary from ACTIVE to EXPOSED on first exposure."""
    timestamp = ts or now_iso()
    exposure_id = f"EXP-{secrets.token_hex(4)}"
    content_sha256 = hashing.block_hash(block_text)

    # Extract session fields
    session_id = _extract(session, "session_id")
    session_id_str = str(session_id) if session_id is not None else ""
    client_key = _extract(session, "client_key")
    classification = _extract(session, "classification")

    # Extract ctx fields
    ip = _extract(ctx, "ip")
    user_agent = _extract(ctx, "user_agent")
    method = _extract(ctx, "method")
    path = _extract(ctx, "path")
    headers = _extract(ctx, "headers") or {}

    referer = None
    accept_language = None
    if isinstance(headers, Mapping):
        for k, v in headers.items():
            k_lower = str(k).lower()
            if k_lower == "referer":
                referer = v
            elif k_lower in ("accept-language", "accept_language"):
                accept_language = v

    client = {
        "ip": ip,
        "user_agent": user_agent,
        "client_key": client_key,
        "classification": classification,
    }
    request = {
        "method": method,
        "path": path,
        "referer": referer,
        "accept_language": accept_language,
    }

    with closing(db.get_connection()) as conn, conn:
        row = conn.execute(
            "SELECT status, content_version FROM canaries WHERE canary_id = ?",
            (canary_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown canary: {canary_id}")

        content_version = row["content_version"]
        current_status = row["status"]

        conn.execute(
            """
            INSERT INTO exposures (
                exposure_id, canary_id, ts, session_id, resource,
                content_version, content_sha256, client, request
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exposure_id,
                canary_id,
                timestamp,
                session_id_str,
                resource,
                content_version,
                content_sha256,
                json.dumps(client),
                json.dumps(request),
            ),
        )

        if current_status == "ACTIVE":
            conn.execute(
                "UPDATE canaries SET status = 'EXPOSED' WHERE canary_id = ?",
                (canary_id,),
            )

    return ExposureEvent(
        exposure_id=exposure_id,
        canary_id=canary_id,
        ts=timestamp,
        session_id=session_id_str,
        resource=resource,
        content_version=content_version,
        content_sha256=content_sha256,
        client=client,
        request=request,
    )


def list_exposures(canary_id: str | None = None) -> list[ExposureEvent]:
    """List exposure events ordered by ts ascending, optionally filtered by canary_id."""
    with closing(db.get_connection()) as conn, conn:
        if canary_id is not None:
            rows = conn.execute(
                "SELECT * FROM exposures WHERE canary_id = ? ORDER BY ts ASC",
                (canary_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM exposures ORDER BY ts ASC"
            ).fetchall()
        return [_row_to_exposure(r) for r in rows]


def set_status(canary_id: str, status: str) -> Canary:
    """Transition canary status. Allowed: ACTIVE->EXPOSED, EXPOSED->OBSERVED, same-status no-op."""
    with closing(db.get_connection()) as conn, conn:
        row = conn.execute("SELECT * FROM canaries WHERE canary_id = ?", (canary_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown canary: {canary_id}")

        current_status = row["status"]
        if current_status == status:
            return _row_to_canary(row)

        if (current_status, status) in [("ACTIVE", "EXPOSED"), ("EXPOSED", "OBSERVED")]:
            conn.execute(
                "UPDATE canaries SET status = ? WHERE canary_id = ?",
                (status, canary_id),
            )
            updated_row = conn.execute("SELECT * FROM canaries WHERE canary_id = ?", (canary_id,)).fetchone()
            return _row_to_canary(updated_row)

        raise InvalidTransition(f"Cannot transition canary {canary_id} from {current_status} to {status}")


def injected_block_text(canary: Canary) -> str:
    """Return the raw block text of the canary for injection (<p>...</p>)."""
    return canary.canonical_content
