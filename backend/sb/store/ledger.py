"""PRD 3.0 baseline forensic append-only ledger helper (Hard Rule 6).

Implements:
- sb.store.ledger.append_event(kind: str, record: dict) -> dict
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


def append_event(kind: str, record: dict) -> dict[str, Any]:
    """Append one event to the append-only forensic ledger.

    Atomically executes BEGIN IMMEDIATE tail + insert across connections and processes.
    Raises OperationalError if forensic_ledger table is missing (never silently recreates lost history).

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

    with _ledger_lock:
        conn = get_connection()
        try:
            conn.isolation_level = None  # Autocommit mode to allow explicit BEGIN IMMEDIATE
            conn.execute("BEGIN IMMEDIATE")

            # Check table exists; missing established table must fail visibly
            tbl_check = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='forensic_ledger'"
            ).fetchone()
            if tbl_check is None:
                conn.execute("ROLLBACK")
                raise sqlite3.OperationalError("forensic_ledger table missing: cannot append to uninitialized or dropped ledger")

            row = conn.execute(
                "SELECT seq, hash FROM forensic_ledger ORDER BY seq DESC LIMIT 1"
            ).fetchone()

            if row is not None:
                seq = int(row["seq"]) + 1
                prev_hash = str(row["hash"])
            else:
                seq = 1
                prev_hash = GENESIS

            ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            envelope = {
                "seq": seq,
                "kind": kind,
                "ts": ts,
                "record": record,
            }
            envelope_bytes = canonical_json_bytes(envelope)
            curr_hash = _compute_hash(prev_hash, envelope_bytes)
            record_str = canonical_json_bytes(record).decode("utf-8")

            conn.execute(
                """
                INSERT INTO forensic_ledger (seq, kind, record, prev_hash, hash, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (seq, kind, record_str, prev_hash, curr_hash, ts),
            )
            conn.execute("COMMIT")

            return {
                "seq": seq,
                "kind": kind,
                "record": record,
                "prev_hash": prev_hash,
                "hash": curr_hash,
                "ts": ts,
            }
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()


def verify_chain() -> dict[str, Any]:
    """Verify cryptographic integrity of the forensic ledger (Hard Rule 6).

    Reconstructs full event envelope {seq, kind, ts, record} for each row.
    Detects record and metadata tampering (altered seq, kind, ts, or prev_hash).
    Missing forensic table => TAMPERED.
    Empty initialized table => VALID (count 0).

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
                except Exception as exc:
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
                except Exception as exc:
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
