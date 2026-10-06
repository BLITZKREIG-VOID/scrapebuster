"""Durable session canary bindings and atomic sequence allocation for W2."""

from __future__ import annotations

import sqlite3
import threading
from typing import Any

from .db import get_connection

_seq_lock = threading.Lock()


def _ensure_canary_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_canary_bindings (
            canary_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            vector TEXT,
            ts TEXT,
            value TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_canary_sequences (
            session_id TEXT PRIMARY KEY,
            next_seq INTEGER NOT NULL
        )
        """
    )


def reserve_canary_sequence(session_id: str) -> int:
    """Atomically allocate and return the next sequential integer (1, 2, ...) for session_id.

    Guarantees concurrency safety via thread locking and SQLite transactions,
    and restart durability via the session_canary_sequences table with fallback
    to existing session_canary_bindings count if uninitialized.
    """
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id must be a non-empty string")

    with _seq_lock:
        conn = get_connection()
        try:
            with conn:
                _ensure_canary_tables(conn)

                row = conn.execute(
                    "SELECT next_seq FROM session_canary_sequences WHERE session_id = ?",
                    (session_id,),
                ).fetchone()

                if row is not None:
                    allocated = int(row["next_seq"])
                    conn.execute(
                        "UPDATE session_canary_sequences SET next_seq = ? WHERE session_id = ?",
                        (allocated + 1, session_id),
                    )
                    return allocated
                else:
                    cnt_row = conn.execute(
                        "SELECT COUNT(*) AS cnt FROM session_canary_bindings WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
                    count = int(cnt_row["cnt"]) if cnt_row else 0
                    allocated = count + 1
                    conn.execute(
                        "INSERT INTO session_canary_sequences (session_id, next_seq) VALUES (?, ?)",
                        (session_id, allocated + 1),
                    )
                    return allocated
        finally:
            conn.close()


def save_canary_binding(
    canary_id: str,
    session_id: str,
    vector: str = "",
    ts: str = "",
    value: str = "",
) -> None:
    """Insert or update a session canary binding row."""
    with _seq_lock:
        conn = get_connection()
        try:
            with conn:
                _ensure_canary_tables(conn)
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
                    (canary_id, session_id, vector, ts, value),
                )
        finally:
            conn.close()


def get_canary_binding(canary_id: str) -> dict[str, Any] | None:
    """Retrieve one session canary binding by canary_id."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT canary_id, session_id, vector, ts, value FROM session_canary_bindings WHERE canary_id = ?",
            (canary_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "canary_id": str(row["canary_id"]),
            "session_id": str(row["session_id"]),
            "vector": str(row["vector"] or ""),
            "ts": str(row["ts"] or ""),
            "value": str(row["value"] or ""),
        }
    finally:
        conn.close()


def list_canary_bindings(session_id: str | None = None) -> list[dict[str, Any]]:
    """List session canary bindings, optionally filtered by session_id."""
    conn = get_connection()
    try:
        if session_id:
            rows = conn.execute(
                "SELECT canary_id, session_id, vector, ts, value FROM session_canary_bindings WHERE session_id = ? ORDER BY ts ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT canary_id, session_id, vector, ts, value FROM session_canary_bindings ORDER BY ts ASC"
            ).fetchall()
        return [
            {
                "canary_id": str(r["canary_id"]),
                "session_id": str(r["session_id"]),
                "vector": str(r["vector"] or ""),
                "ts": str(r["ts"] or ""),
                "value": str(r["value"] or ""),
            }
            for r in rows
        ]
    finally:
        conn.close()
