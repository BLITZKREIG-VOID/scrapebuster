"""PRD 3.0 baseline forensic append-only ledger helper (Hard Rule 6 & Phase 1 batch persistence).

Implements:
- sb.store.ledger.append_event(kind: str, record: dict, conn=None) -> dict
- sb.store.ledger.append_events_batch(events: list[tuple[str, dict]], conn=None) -> list[dict]
- sb.store.ledger.persist_telemetry_batch(events: list[dict], session_updates: list[dict], conn=None) -> None
- sb.store.ledger.verify_chain() -> dict
- Hash canonical full event envelope {seq, kind, ts, record}
- Single canonical JSON SHA256 H_prev||envelope byte encoding
- Explicit sequence and prev_hash/hash
- Atomic transactional BEGIN IMMEDIATE tail + insert across connections/processes
- Append-only forensic ledger table database update/delete guard
- Missing forensic table => TAMPERED, empty initialized table => VALID 0
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from datetime import UTC, datetime
from typing import Any

from .db import _lock, get_connection

logger = logging.getLogger("sb.store.ledger")

GENESIS: str = "0" * 64
_ledger_lock = threading.RLock()


def _json_default(obj: Any) -> Any:
    """Fallback serializer for Pydantic models or objects with model_dump/dict/to_dict."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json_bytes(record: Any) -> bytes:
    """Encode record into canonical UTF-8 JSON bytes with sorted keys, compact separators, and allow_nan=False."""
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")


def _compute_hash(prev_hash: str, envelope_bytes: bytes) -> str:
    """Compute SHA-256 over canonical byte concatenation: H_prev || envelope_bytes.

    prev_hash encoding documented:
        UTF-8 encoded hex string of the previous event hash (or GENESIS = '0'*64 for seq 1).
    envelope encoding:
        Canonical UTF-8 JSON bytes of {'seq': seq, 'kind': kind, 'ts': ts, 'record': record}.
    """
    payload = prev_hash.encode("utf-8") + envelope_bytes
    return hashlib.sha256(payload).hexdigest()


def append_events_batch(
    events: list[tuple[str, dict[str, Any]]],
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Atomically append a batch of events to the append-only forensic ledger.

    Atomically computes sequential hashes and inserts envelopes inside a single BEGIN IMMEDIATE
    transaction under _ledger_lock.
    Raises OperationalError if forensic_ledger table is missing (never silently recreates lost history).
    If an existing connection is passed, caller manages the transaction context.
    Rolls back entire transaction on any failure without silent ignoring.

    Returns list of appended event dictionaries:
        [
            {
                "seq": int,
                "kind": str,
                "record": dict,
                "prev_hash": str,
                "hash": str,
                "ts": str,
            },
            ...
        ]
    """
    if not isinstance(events, list):
        raise TypeError(f"events must be a list of (kind, record) tuples, got {type(events).__name__}")

    if not events:
        return []

    for item in events:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise TypeError("each event in batch must be a 2-tuple (kind, record)")
        kind, record = item
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("kind must be a non-empty string")
        if not isinstance(record, dict) and not hasattr(record, "to_dict"):
            raise TypeError(f"record must be a dict, got {type(record).__name__}")

    manage_conn = conn is None
    with _ledger_lock:
        target_conn = get_connection() if manage_conn else conn
        assert target_conn is not None
        try:
            if manage_conn:
                target_conn.isolation_level = None  # Autocommit mode for explicit BEGIN IMMEDIATE
                target_conn.execute("BEGIN IMMEDIATE")

            # Check table exists; missing established table must fail visibly
            tbl_check = target_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='forensic_ledger'"
            ).fetchone()
            if tbl_check is None:
                if manage_conn:
                    target_conn.execute("ROLLBACK")
                raise sqlite3.OperationalError(
                    "forensic_ledger table missing: cannot append to uninitialized or dropped ledger"
                )

            tail_row = target_conn.execute(
                "SELECT seq, hash FROM forensic_ledger ORDER BY seq DESC LIMIT 1"
            ).fetchone()

            if tail_row is not None:
                current_seq = int(tail_row["seq"])
                current_prev_hash = str(tail_row["hash"])
            else:
                current_seq = 0
                current_prev_hash = GENESIS

            appended_results: list[dict[str, Any]] = []
            insert_rows = []

            for item in events:
                kind, record_obj = item
                record = record_obj.to_dict() if hasattr(record_obj, "to_dict") else dict(record_obj)

                current_seq += 1
                seq = current_seq
                prev_hash = current_prev_hash
                ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")

                envelope = {
                    "seq": seq,
                    "kind": kind,
                    "ts": ts,
                    "record": record,
                }
                envelope_bytes = canonical_json_bytes(envelope)
                curr_hash = _compute_hash(prev_hash, envelope_bytes)
                record_str = canonical_json_bytes(record).decode("utf-8")

                insert_rows.append((seq, kind, record_str, prev_hash, curr_hash, ts))
                appended_results.append({
                    "seq": seq,
                    "kind": kind,
                    "record": record,
                    "prev_hash": prev_hash,
                    "hash": curr_hash,
                    "ts": ts,
                })
                current_prev_hash = curr_hash

            target_conn.executemany(
                """
                INSERT INTO forensic_ledger (seq, kind, record, prev_hash, hash, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                insert_rows,
            )

            if manage_conn:
                target_conn.execute("COMMIT")

            return appended_results
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


def append_event(
    kind: str,
    record: dict[str, Any],
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Append one event to the append-only forensic ledger.

    Delegates to append_events_batch for atomic hash chaining.
    """
    results = append_events_batch([(kind, record)], conn=conn)
    return results[0]


def persist_telemetry_batch(
    events: list[dict[str, Any]],
    session_updates: list[dict[str, Any]],
    conn: sqlite3.Connection | None = None,
) -> None:
    """Atomic transactional telemetry persistence coupling operational projections and ledger.

    Simultaneously updates mutable operational projections (traffic_events, sessions)
    AND appends immutable forensic records to forensic_ledger within the exact same database transaction.
    Consistent locking ordering: acquires _lock (DB) then _ledger_lock.
    Pair list order is strictly preserved.
    Any failure or invalid state triggers a full rollback and raises visibly (no silent ignore).
    """
    from .sessions import upsert_sessions_batch
    from .traffic import insert_traffic_events_batch

    if not isinstance(events, list) or not isinstance(session_updates, list):
        raise TypeError("events and session_updates must be lists of dictionaries")

    if not events and not session_updates:
        return

    manage_conn = conn is None
    with _lock, _ledger_lock:
        target_conn = get_connection() if manage_conn else conn
        assert target_conn is not None
        try:
            if manage_conn:
                target_conn.isolation_level = None
                target_conn.execute("BEGIN IMMEDIATE")

            # 1. Update mutable operational projections inside same transaction
            if events:
                insert_traffic_events_batch(events, conn=target_conn)
            if session_updates:
                upsert_sessions_batch(session_updates, conn=target_conn)

            # 2. Prepare coupled immutable forensic records preserving pair list order
            ledger_items: list[tuple[str, dict[str, Any]]] = []
            max_len = max(len(events), len(session_updates))
            for i in range(max_len):
                if i < len(events):
                    ledger_items.append(("traffic", events[i]))
                if i < len(session_updates):
                    ledger_items.append(("session_snapshot", session_updates[i]))

            # 3. Append to forensic ledger on the exact SAME connection inside transaction
            if ledger_items:
                append_events_batch(ledger_items, conn=target_conn)

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


def verify_chain() -> dict[str, Any]:
    """Verify cryptographic integrity of the forensic ledger (Hard Rule 6).

    Reconstructs full event envelope {seq, kind, ts, record} for each row.
    Detects record and metadata tampering (altered seq, kind, ts, or prev_hash).
    Missing forensic table => TAMPERED.
    Empty initialized table => VALID (count 0).

    Returns exact existing shape:
        {
            "result": "VALID" | "TAMPERED",
            "count": int,
            "head": str,
            "errors": list[str],
        }
    """
    with _ledger_lock:
        conn = get_connection()
        try:
            tbl_check = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='forensic_ledger'"
            ).fetchone()
            if tbl_check is None:
                return {
                    "result": "TAMPERED",
                    "count": 0,
                    "head": GENESIS,
                    "errors": ["Forensic table missing: forensic_ledger table does not exist"],
                }

            rows = conn.execute(
                "SELECT seq, kind, record, prev_hash, hash, ts FROM forensic_ledger ORDER BY seq ASC"
            ).fetchall()

            if not rows:
                return {
                    "result": "VALID",
                    "count": 0,
                    "head": GENESIS,
                    "errors": [],
                }

            errors: list[str] = []
            expected_seq = 1
            expected_prev_hash = GENESIS

            for r in rows:
                r_seq = int(r["seq"])
                r_kind = str(r["kind"])
                r_raw = str(r["record"])
                r_prev = str(r["prev_hash"])
                r_hash = str(r["hash"])
                r_ts = str(r["ts"])

                if r_seq != expected_seq:
                    errors.append(f"Sequence gap at seq {r_seq}: expected {expected_seq}")

                if r_prev != expected_prev_hash:
                    errors.append(
                        f"prev_hash mismatch at seq {r_seq}: expected {expected_prev_hash}, got {r_prev}"
                    )

                try:
                    rec_obj = json.loads(r_raw)
                except (ValueError, TypeError) as exc:
                    errors.append(f"Invalid record JSON encoding at seq {r_seq}: {exc}")
                    rec_obj = r_raw

                envelope = {
                    "seq": r_seq,
                    "kind": r_kind,
                    "ts": r_ts,
                    "record": rec_obj,
                }
                try:
                    envelope_bytes = canonical_json_bytes(envelope)
                except (ValueError, TypeError, OverflowError, RecursionError) as exc:
                    errors.append(f"Failed to canonicalize envelope at seq {r_seq}: {exc}")
                    envelope_bytes = b""

                computed_hash = _compute_hash(r_prev, envelope_bytes)
                if r_hash != computed_hash:
                    errors.append(
                        f"Hash mismatch at seq {r_seq}: computed {computed_hash}, recorded {r_hash}"
                    )

                expected_seq = r_seq + 1
                expected_prev_hash = r_hash

            head = rows[-1]["hash"] if rows else GENESIS
            result = "VALID" if not errors else "TAMPERED"

            return {
                "result": result,
                "count": len(rows),
                "head": head,
                "errors": errors,
            }
        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError) as exc:
            return {
                "result": "TAMPERED",
                "count": 0,
                "head": GENESIS,
                "errors": [f"Verification exception: {exc}"],
            }
        finally:
            conn.close()


def get_ledger_head() -> str:
    """Return the hash of the latest event in the ledger, or GENESIS if empty."""
    with _ledger_lock:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT hash FROM forensic_ledger ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            return str(row["hash"]) if row else GENESIS
        except sqlite3.Error:
            return GENESIS
        finally:
            conn.close()


def get_ledger_events(limit: int | None = None) -> list[dict[str, Any]]:
    """Return ledger events ordered by sequence ascending."""
    with _ledger_lock:
        conn = get_connection()
        try:
            query = "SELECT seq, kind, record, prev_hash, hash, ts FROM forensic_ledger ORDER BY seq ASC"
            if limit is not None:
                query += f" LIMIT {int(limit)}"
            rows = conn.execute(query).fetchall()
            events = []
            for r in rows:
                events.append({
                    "seq": int(r["seq"]),
                    "kind": str(r["kind"]),
                    "record": json.loads(r["record"]),
                    "prev_hash": str(r["prev_hash"]),
                    "hash": str(r["hash"]),
                    "ts": str(r["ts"]),
                })
            return events
        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
            return []
        finally:
            conn.close()
