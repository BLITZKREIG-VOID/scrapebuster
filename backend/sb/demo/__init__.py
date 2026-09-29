"""Demo control: reset (§21), runner (§20), golden run (§21). Owner: Arnav.

Cross-owner dependencies are resolved lazily through :func:`require` so a missing
subsystem surfaces as a named failure (never a silent skip):

* ``sb.store.db.reset_db`` / ``DB_PATH``   — INT-03 (Anirudh)
* ``sb.edge.session.sessions.reset``       — INT-04 (Anirudh): in-memory edge sessions
* ``sb.hooks.trap_hooks.reset`` and the ``sb.hooks.register_reset_hook`` registry
  (``run_reset_hooks``) — INT-04 (Anirudh); trap (TRP-01/02) and provenance (PRV-01) by Hardik
* ``sb.canary.seed.seed_canaries``         — CAN-01 (Hardik)

``demo_state`` (§15) is read/written through a separate stdlib sqlite3 connection on the
store's own ``DB_PATH`` (WAL mode, so a second connection is safe). String values are
stored raw (``/api/v1/overview`` reads ``run_id`` directly); structured values as JSON.
"""
import importlib
import json
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATASETS_DIR = REPO / "data" / "datasets"
CONTROL_DATASET = REPO / "data" / "control" / "control_clean.jsonl"
EVIDENCE_DIR = REPO / "evidence"
GOLDEN_DIR = REPO / "data" / "golden"
ATTACKS_DIR = REPO / "attacks"

EDGE_URL = os.environ.get("SB_EDGE_URL", "http://127.0.0.1:8000")
ORIGIN_URL = os.environ.get("SB_ORIGIN_URL", "http://127.0.0.1:8001")
OLLAMA_URL = os.environ.get("SB_OLLAMA_URL", "http://127.0.0.1:11434")

# One lock for reset / run / golden restore (§21 step 1: reset refuses while a run holds it).
RUN_LOCK = threading.Lock()


class DemoBusy(RuntimeError):
    """A demo run/reset/restore currently holds the run lock (HTTP 409)."""


class MissingDependency(RuntimeError):
    """A cross-owner module/attribute this code relies on does not exist yet."""


def require(module: str, attr: str, owner: str):
    try:
        mod = importlib.import_module(module)
    except ImportError as exc:
        raise MissingDependency(f"{module} missing ({owner}): {exc}") from exc
    try:
        return getattr(mod, attr)
    except AttributeError as exc:
        raise MissingDependency(f"{module}.{attr} missing ({owner})") from exc


def db_path() -> Path:
    """The store's own DB path (INT-03); ``SB_DB_PATH`` only when the store is absent."""
    try:
        from sb.store.db import DB_PATH
    except ImportError:
        DB_PATH = os.environ.get("SB_DB_PATH", "backend/sb.db")
    path = Path(DB_PATH)
    return (path if path.is_absolute() else REPO / path).resolve()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path(), timeout=10, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("CREATE TABLE IF NOT EXISTS demo_state (key TEXT PRIMARY KEY, value TEXT)")
        yield conn
    finally:
        conn.close()


def get_state(key: str, default=None):
    with connect() as conn:
        row = conn.execute("SELECT value FROM demo_state WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    value = row["value"]
    return json.loads(value) if value[:1] in ("{", "[") else value


def set_state(key: str, value) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO demo_state(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value if isinstance(value, str) else json.dumps(value)),
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
