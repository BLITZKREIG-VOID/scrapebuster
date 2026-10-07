import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone

logger = logging.getLogger("sb.store.db")

DB_PATH = os.getenv("SB_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "sb.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

_lock = threading.RLock()

# Authoritative tables preserved across operational resets
PRESERVED_TABLES = frozenset({
    "forensic_ledger",
    "session_canary_bindings",
    "session_canary_sequences",
    "sqlite_sequence",
    "app_state",
})


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Idempotently initialize database schema, tables, and triggers.

    Enforces Missing History Guard (Phase 0 Hard Rule 6):
    - Fresh empty DB: Bootstraps complete schema including forensic_ledger and sets durable initialized marker.
    - Already initialized DB: If forensic_ledger is missing, refuses to silently recreate genesis and raises
      OperationalError (TAMPERED). Re-creation of dropped audit history is strictly prohibited.
    """
    with _lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            total_user_tables = cursor.fetchone()[0]

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_state'")
            has_app_state = cursor.fetchone() is not None

            is_initialized = False
            if has_app_state:
                row = cursor.execute("SELECT value FROM app_state WHERE key='initialized'").fetchone()
                if row is not None and str(row[0]) == "1":
                    is_initialized = True

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='forensic_ledger'")
            has_ledger = cursor.fetchone() is not None

            if total_user_tables > 0:
                # Established non-empty database: reject bootstrap if missing initialized marker or ledger
                if not is_initialized or not has_ledger:
                    raise sqlite3.OperationalError(
                        "Non-empty database lacks valid initialization marker or forensic_ledger: "
                        "database is TAMPERED or unsupported old store; refusing to silently recreate dropped audit history"
                    )

            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema_script = f.read()

            if total_user_tables == 0:
                # Fresh empty DB bootstrap
                conn.executescript(schema_script)
                conn.execute(
                    "INSERT OR REPLACE INTO app_state (key, value) VALUES ('initialized', '1')"
                )
                conn.commit()
            else:
                # Existing valid DB: ensure non-ledger projections/tables exist without altering ledger
                conn.executescript(schema_script)
                conn.commit()
        finally:
            conn.close()


def reset_db() -> None:
    """Operational database reset.

    Preserves authoritative forensic_ledger, canary counters (session_canary_sequences),
    durable bindings (session_canary_bindings), and durable initialized marker (app_state).
    Resets read projection tables atomically and appends an authoritative reset audit event to the ledger
    in a single atomic transaction.
    """
    from .ledger import _ledger_lock, append_event

    with _lock, _ledger_lock:
        init_db()  # Verifies schema and checks tamper guard

        conn = get_connection()
        try:
            conn.isolation_level = None
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                if table not in PRESERVED_TABLES and not table.startswith("sqlite_"):
                    conn.execute(f"DELETE FROM {table}")

            # Append authoritative reset audit event to the forensic ledger on the SAME connection

            append_event(
                "reset",
                {
                    "reason": "operational_reset",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                },
                conn=conn,
            )

            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()


# Initialize DB on load if it doesn't exist
if not os.path.exists(DB_PATH):
    try:
        init_db()
    except Exception as exc:
        logger.error("Could not auto-initialize DB on import: %s", exc)
