"""PRD 3.0 baseline forensic append-only ledger helper (Hard Rule 6).

Implements:
- sb.store.ledger.append_event(kind: str, record: dict) -> dict
- sb.store.ledger.verify_chain() -> dict
- Single canonical JSON SHA256 H_prev||record byte encoding
- Explicit sequence and prev_hash/hash
- Atomic transactional tail + insert
- Append-only forensic ledger table database update/delete guard
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from .db import get_connection

GENESIS: str = "0" * 64
_ledger_lock = threading.Lock()


def _json_default(obj: Any) -> Any:
    """Fallback serializer for Pydantic models or objects with model_dump/dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json_bytes(record: Any) -> bytes:
    """Encode record into canonical UTF-8 JSON bytes with sorted keys and compact separators."""
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")


def _compute_hash(prev_hash: str, record_bytes: bytes) -> str:
    """Compute SHA-256 over canonical byte concatenation: H_prev || record."""
    payload = prev_hash.encode("utf-8") + record_bytes
    return hashlib.sha256(payload).hexdigest()


def _ensure_ledger_table(conn: sqlite3.Connection) -> None:
    """Ensure forensic_ledger table and update/delete guard triggers exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS forensic_ledger (
            seq INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,
            record TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL,
            ts TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS prevent_ledger_update
        BEFORE UPDATE ON forensic_ledger
        BEGIN
            SELECT RAISE(ABORT, 'forensic_ledger is append-only: updates prohibited');
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS prevent_ledger_delete
        BEFORE DELETE ON forensic_ledger
        BEGIN
            SELECT RAISE(ABORT, 'forensic_ledger is append-only: deletes prohibited');
        END
        """
    )


def append_event(kind: str, record: dict) -> dict[str, Any]:
    """Append one event to the append-only forensic ledger.

    Returns event metadata:
        {
            "seq": int,
            "kind": str,
            "record": dict,
            "prev_hash": str,
            "hash": str,
            "ts": str,
        }
    """
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("kind must be a non-empty string")
    if not isinstance(record, dict):
        raise TypeError(f"record must be a dict, got {type(record).__name__}")

    record_bytes = canonical_json_bytes(record)
    record_str = record_bytes.decode("utf-8")

    with _ledger_lock:
        conn = get_connection()
        try:
            with conn:
                _ensure_ledger_table(conn)

                row = conn.execute(
                    "SELECT seq, hash FROM forensic_ledger ORDER BY seq DESC LIMIT 1"
                ).fetchone()

                if row is not None:
                    seq = int(row["seq"]) + 1
                    prev_hash = str(row["hash"])
                else:
                    seq = 1
                    prev_hash = GENESIS

                curr_hash = _compute_hash(prev_hash, record_bytes)
                ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

                conn.execute(
                    """
                    INSERT INTO forensic_ledger (seq, kind, record, prev_hash, hash, ts)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (seq, kind, record_str, prev_hash, curr_hash, ts),
                )

                return {
                    "seq": seq,
                    "kind": kind,
                    "record": record,
                    "prev_hash": prev_hash,
                    "hash": curr_hash,
                    "ts": ts,
                }
        finally:
            conn.close()


def verify_chain() -> dict[str, Any]:
    """Verify cryptographic integrity of the forensic ledger (Hard Rule 6).

    Verifies strict sequence continuity (1, 2, 3...), prev_hash chaining from GENESIS,
    and single canonical JSON SHA-256 H_prev||record byte encoding integrity.
    Never invents VALID on errors or discrepancies.

    Returns:
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
                    "result": "VALID",
                    "count": 0,
                    "head": GENESIS,
                    "errors": [],
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

                if r_seq != expected_seq:
                    errors.append(f"Sequence gap at seq {r_seq}: expected {expected_seq}")

                if r_prev != expected_prev_hash:
                    errors.append(
                        f"prev_hash mismatch at seq {r_seq}: expected {expected_prev_hash}, got {r_prev}"
                    )

                try:
                    rec_obj = json.loads(r_raw)
                    rec_bytes = canonical_json_bytes(rec_obj)
                except Exception as exc:
                    errors.append(f"Invalid record JSON encoding at seq {r_seq}: {exc}")
                    rec_bytes = r_raw.encode("utf-8")

                computed_hash = _compute_hash(r_prev, rec_bytes)
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
        except Exception as exc:
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
        except Exception:
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
        except Exception:
            return []
        finally:
            conn.close()
