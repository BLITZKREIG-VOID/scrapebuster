"""Canary registry: persistence, status transitions, publications, exposures."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SessionCanaryBinding:
    """Runtime binding for session-bound canaries."""
    canary_id: str
    session_id: str
    vector: str
    ts: str
    value: str


_session_bindings_cache: dict[str, SessionCanaryBinding] = {}


def now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format with microsecond precision and Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def normalize_vector(vector: str) -> str:
    """Normalize vector identifiers to PRD standard (API/TEXT/JSONLD/BEACON/DNS/HONEYKEY)."""
    v = (vector or "").strip()
    v_upper = v.upper()
    if v_upper in ("HTML", "TEXT"):
        return "TEXT"
    if v_upper in ("JSON", "API"):
        return "API"
    if v_upper in ("JSONLD", "BEACON", "DNS", "HONEYKEY"):
        return v_upper
    return v_upper or "TEXT"


def _ensure_bindings_table(conn: sqlite3.Connection) -> None:
    """Ensure session_canary_bindings table exists in SQLite database."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_canary_bindings (
            canary_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            vector TEXT NOT NULL,
            ts TEXT NOT NULL,
            value TEXT NOT NULL
        )
        """
    )


def reserve_canary_sequence(session_id: str) -> int:
    """Atomically reserve next canary sequence counter for a session.

    Delegates to sb.store.reserve_canary_sequence if available; otherwise uses
    durable SQLite sequence table.
    """
    clean_session = str(session_id or "anonymous")
    try:
        import sb.store
        if hasattr(sb.store, "reserve_canary_sequence"):
            return sb.store.reserve_canary_sequence(clean_session)
    except Exception:
        pass

    with closing(db.get_connection()) as conn, conn:
        _ensure_bindings_table(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS canary_sequences (
                session_id TEXT PRIMARY KEY,
                seq INT NOT NULL
            )
            """
        )
        row = conn.execute(
            "SELECT seq FROM canary_sequences WHERE session_id = ?",
            (clean_session,),
        ).fetchone()
        if row is None:
            count_row = conn.execute(
                "SELECT count(*) as c FROM session_canary_bindings WHERE session_id = ?",
                (clean_session,),
            ).fetchone()
            current_count = count_row["c"] if count_row else 0
            new_seq = current_count + 1
            conn.execute(
                "INSERT INTO canary_sequences (session_id, seq) VALUES (?, ?)",
                (clean_session, new_seq),
            )
            return new_seq
        else:
            new_seq = row["seq"] + 1
            conn.execute(
                "UPDATE canary_sequences SET seq = ? WHERE session_id = ?",
                (new_seq, clean_session),
            )
            return new_seq


def append_event(kind: str, record: dict) -> dict:
    """Append a chained event to the ledger.

    Delegates to sb.store.ledger.append_event if available; otherwise persists
    to local SQLite ledger_events table with cryptographic hash chaining.
    """
    try:
        from sb.store import ledger as store_ledger
        if hasattr(store_ledger, "append_event"):
            return store_ledger.append_event(kind, record)
    except Exception:
        pass

    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                record TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                hash TEXT NOT NULL,
                ts TEXT NOT NULL
            )
            """
        )
        last_row = conn.execute(
            "SELECT seq, hash FROM ledger_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = last_row["hash"] if last_row else "0" * 64
        timestamp = now_iso()
        record_json = json.dumps(record, sort_keys=True)
        payload = f"{prev_hash}:{kind}:{record_json}:{timestamp}"
        event_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        cursor = conn.execute(
            """
            INSERT INTO ledger_events (kind, record, prev_hash, hash, ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            (kind, record_json, prev_hash, event_hash, timestamp),
        )
        seq = cursor.lastrowid
        return {
            "seq": seq,
            "kind": kind,
            "record": record,
            "prev_hash": prev_hash,
            "hash": event_hash,
            "ts": timestamp,
        }


def verify_chain() -> dict:
    """Verify cryptographic integrity of the hash-chained ledger."""
    try:
        from sb.store import ledger as store_ledger
        if hasattr(store_ledger, "verify_chain"):
            return store_ledger.verify_chain()
    except Exception:
        pass

    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                record TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                hash TEXT NOT NULL,
                ts TEXT NOT NULL
            )
            """
        )
        rows = conn.execute("SELECT * FROM ledger_events ORDER BY seq ASC").fetchall()
        expected_prev = "0" * 64
        errors: list[str] = []
        for r in rows:
            if r["prev_hash"] != expected_prev:
                errors.append(f"Broken chain at seq {r['seq']}: expected prev {expected_prev}, got {r['prev_hash']}")
            payload = f"{r['prev_hash']}:{r['kind']}:{r['record']}:{r['ts']}"
            computed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if r["hash"] != computed:
                errors.append(f"Hash mismatch at seq {r['seq']}: expected {computed}, got {r['hash']}")
            expected_prev = r["hash"]

        status = "VALID" if not errors else "TAMPERED"
        head = expected_prev if rows else "0" * 64
        return {
            "result": status,
            "count": len(rows),
            "head": head,
            "errors": errors,
        }


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
        d["placements"] = json.loads(val)
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


def bind_session_canary(
    session_id: str,
    vector: str = "html",
    value: str | None = None,
    ts: str | None = None,
) -> SessionCanaryBinding:
    """Generate and bind a runtime session canary: SB-CANARY-<session_hash>-<seq>.

    Binds canary_id, session_id, vector, ts, value durably in SQLite.
    Appends a chained canary_binding event to the ledger.
    Does not swallow DB registration errors.
    """
    clean_session = str(session_id or "anonymous")
    norm_vector = normalize_vector(vector)
    seq = reserve_canary_sequence(clean_session)
    session_hash = hashlib.sha256(clean_session.encode("utf-8")).hexdigest()[:8]
    canary_id = f"SB-CANARY-{session_hash}-{seq:04d}"
    timestamp = ts or now_iso()
    canary_val = value or f"CONFIDENTIAL-REF-{canary_id}"

    binding = SessionCanaryBinding(
        canary_id=canary_id,
        session_id=clean_session,
        vector=norm_vector,
        ts=timestamp,
        value=canary_val,
    )

    with closing(db.get_connection()) as conn, conn:
        _ensure_bindings_table(conn)
        conn.execute(
            """
            INSERT INTO session_canary_bindings (canary_id, session_id, vector, ts, value)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(canary_id) DO UPDATE SET
                session_id = excluded.session_id,
                vector = excluded.vector,
                ts = excluded.ts,
                value = excluded.value
            """,
            (canary_id, clean_session, norm_vector, timestamp, canary_val),
        )

    # Persist in canaries table so downstream foreign references succeed (DO NOT swallow write errors)
    upsert_canary({
        "canary_id": canary_id,
        "type": f"session_{norm_vector.lower()}",
        "canonical_content": canary_val,
        "anchor": canary_id,
        "context_terms": [clean_session, norm_vector],
        "probe_prompts": [],
        "sha256": hashing.block_hash(canary_val),
        "content_version": "v1",
        "created_at": timestamp,
        "published_at": timestamp,
        "status": "ACTIVE",
        "placements": [],
    })

    # Record chained binding event
    binding_record = {
        "canary_id": canary_id,
        "session_id": clean_session,
        "vector": norm_vector,
        "ts": timestamp,
        "value": canary_val,
    }
    append_event("canary_binding", binding_record)

    _session_bindings_cache[canary_id] = binding
    return binding


def get_session_binding(canary_id: str) -> SessionCanaryBinding | None:
    """Retrieve session canary binding by canary_id from SQLite durable storage."""
    cached = _session_bindings_cache.get(canary_id)
    if cached is not None:
        return cached

    with closing(db.get_connection()) as conn, conn:
        _ensure_bindings_table(conn)
        row = conn.execute(
            "SELECT canary_id, session_id, vector, ts, value FROM session_canary_bindings WHERE canary_id = ?",
            (canary_id,),
        ).fetchone()
        if row is None:
            return None
        binding = SessionCanaryBinding(
            canary_id=row["canary_id"],
            session_id=row["session_id"],
            vector=row["vector"],
            ts=row["ts"],
            value=row["value"],
        )
        _session_bindings_cache[canary_id] = binding
        return binding


def list_session_bindings(session_id: str | None = None) -> list[SessionCanaryBinding]:
    """List session canary bindings from SQLite durable storage, optionally filtered by session_id."""
    with closing(db.get_connection()) as conn, conn:
        _ensure_bindings_table(conn)
        if session_id is not None:
            rows = conn.execute(
                "SELECT canary_id, session_id, vector, ts, value FROM session_canary_bindings WHERE session_id = ? ORDER BY ts ASC, canary_id ASC",
                (str(session_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT canary_id, session_id, vector, ts, value FROM session_canary_bindings ORDER BY ts ASC, canary_id ASC"
            ).fetchall()
        bindings = [
            SessionCanaryBinding(
                canary_id=r["canary_id"],
                session_id=r["session_id"],
                vector=r["vector"],
                ts=r["ts"],
                value=r["value"],
            )
            for r in rows
        ]
        for b in bindings:
            _session_bindings_cache[b.canary_id] = b
        return bindings


def reset_session_bindings() -> None:
    """Reset session canary bindings in SQLite durable storage and clear in-memory cache."""
    _session_bindings_cache.clear()
    with closing(db.get_connection()) as conn, conn:
        _ensure_bindings_table(conn)
        conn.execute("DELETE FROM session_canary_bindings")
        try:
            conn.execute("DELETE FROM canary_sequences")
        except sqlite3.OperationalError:
            pass


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
    anchor = data.get("anchor", "")
    context_terms = data.get("context_terms", [])
    probe_prompts = data.get("probe_prompts", [])
    sha256 = data["sha256"]
    content_version = data.get("content_version", "v1")
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
            # Check if it exists as a durable session binding
            binding = get_session_binding(canary_id)
            if binding is not None:
                return Canary(
                    canary_id=binding.canary_id,
                    type=f"session_{binding.vector.lower()}",
                    canonical_content=binding.value,
                    anchor=binding.canary_id,
                    context_terms=[binding.session_id, binding.vector],
                    probe_prompts=[],
                    sha256=hashing.block_hash(binding.value),
                    content_version="v1",
                    created_at=binding.ts,
                    published_at=binding.ts,
                    status="ACTIVE",
                    placements=[],
                )
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


def record_injection_outcome(
    canary_id: str | None,
    vector: str,
    session_id: str,
    time: str,
    outcome: str,
    error: str | None = None,
    resource: str | None = None,
) -> dict:
    """Record an injection outcome (e.g. fallback) in the chained ledger."""
    norm_vector = normalize_vector(vector)
    rec: dict[str, Any] = {
        "canary_id": canary_id,
        "vector": norm_vector,
        "session_id": str(session_id),
        "time": time,
        "outcome": outcome,
    }
    if error:
        rec["error"] = error
    if resource:
        rec["resource"] = resource
    return append_event("canary_injection", rec)


def record_exposure(
    canary_id: str,
    session: Any,
    ctx: Any,
    resource: str,
    block_text: str,
    ts: str | None = None,
    vector: str | None = None,
    outcome: str = "success",
) -> ExposureEvent:
    """Record an exposure event and transition canary from ACTIVE to EXPOSED on first exposure.

    Appends a chained canary_exposure event to the ledger.
    """
    timestamp = ts or now_iso()
    exposure_id = f"EXP-{secrets.token_hex(4)}"
    content_sha256 = hashing.block_hash(block_text)
    norm_vector = normalize_vector(vector or "html")

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
    request: dict[str, Any] = {
        "method": method,
        "path": path,
        "referer": referer,
        "accept_language": accept_language,
    }
    if vector is not None:
        request["vector"] = norm_vector

    with closing(db.get_connection()) as conn, conn:
        row = conn.execute(
            "SELECT status, content_version FROM canaries WHERE canary_id = ?",
            (canary_id,),
        ).fetchone()

        if row is None:
            # If not in table, check if session binding exists
            binding = get_session_binding(canary_id)
            if binding is None:
                raise KeyError(f"Unknown canary: {canary_id}")
            content_version = "v1"
            current_status = "ACTIVE"
            conn.execute(
                """
                INSERT INTO canaries (
                    canary_id, type, canonical_content, anchor, context_terms,
                    probe_prompts, sha256, content_version, created_at, published_at,
                    status, placements
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    canary_id,
                    f"session_{norm_vector.lower()}",
                    binding.value if binding else block_text,
                    canary_id,
                    json.dumps([session_id_str, norm_vector]),
                    "[]",
                    content_sha256,
                    content_version,
                    timestamp,
                    timestamp,
                    current_status,
                    json.dumps([resource]),
                ),
            )
        else:
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

    # Append chained exposure event to ledger
    exp_record = {
        "exposure_id": exposure_id,
        "canary_id": canary_id,
        "vector": norm_vector,
        "session_id": session_id_str,
        "time": timestamp,
        "outcome": outcome,
        "resource": resource,
    }
    append_event("canary_exposure", exp_record)

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
    """Return the raw block text of the canary for injection."""
    return canary.canonical_content
