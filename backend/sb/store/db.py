import os
import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = os.getenv("SB_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "sb.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

_lock = threading.RLock()

# Authoritative tables preserved across operational resets
PRESERVED_TABLES = frozenset({
    "forensic_ledger",
    "session_canary_bindings",
    "session_canary_sequences",
    "sqlite_sequence",
})


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Idempotently initialize database schema, tables, and triggers."""
    with _lock:
        conn = get_connection()
        try:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema_script = f.read()
            conn.executescript(schema_script)
            conn.commit()
        finally:
            conn.close()


def reset_db() -> None:
    """Operational database reset.

    Preserves authoritative forensic_ledger, canary counters (session_canary_sequences),
    and durable bindings (session_canary_bindings).
    Resets read projection tables only and appends an authoritative reset audit event to the ledger.
    """
    with _lock:
        init_db()  # Ensure schema exists idempotently

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                if table not in PRESERVED_TABLES:
                    conn.execute(f"DELETE FROM {table}")
            conn.commit()
        finally:
            conn.close()

        # Append authoritative reset audit event to the forensic ledger
        from .ledger import append_event

        append_event("reset", {
            "reason": "operational_reset",
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })


# Initialize DB on load if it doesn't exist
if not os.path.exists(DB_PATH):
    init_db()
