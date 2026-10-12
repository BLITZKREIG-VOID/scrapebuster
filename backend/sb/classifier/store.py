"""Durable storage for Route Baselines in ScrapeBuster Phase 2 (PRD FR-2.1, FR-2.5).

Persists per-route asset ratio EMA baselines in embedded SQLite (default)
or configured Redis. Ensures baseline state survives server restarts.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from ..store.db import get_connection

logger = logging.getLogger("sb.classifier.store")

_store_lock = threading.RLock()
_store_conn: sqlite3.Connection | None = None


def _get_store_conn() -> sqlite3.Connection:
    global _store_conn
    if _store_conn is None:
        _store_conn = get_connection()
    return _store_conn


def get_route_baseline(route: str, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    """Retrieve route baseline from persistent store. Returns None if not present."""
    with _store_lock:
        target_conn = conn if conn is not None else _get_store_conn()
        try:
            row = target_conn.execute(
                "SELECT route, ar_ema, sample_count, updated_at FROM route_baselines WHERE route = ?",
                (route,),
            ).fetchone()
            if not row:
                return None
            return {
                "route": str(row["route"]),
                "ar_ema": float(row["ar_ema"]),
                "sample_count": int(row["sample_count"]),
                "updated_at": str(row["updated_at"]),
            }
        except Exception as exc:
            logger.error("Error reading route baseline for %s: %s", route, exc)
            return None


def update_route_baseline(
    route: str,
    ar_current: float,
    alpha: float = 0.2,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Update or create route baseline using exponential moving average (EMA).

    AR_baseline(route) = alpha * AR_current + (1 - alpha) * AR_historical (PRD FR-2.1).
    """
    with _store_lock:
        target_conn = conn if conn is not None else _get_store_conn()
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            row = target_conn.execute(
                "SELECT ar_ema, sample_count FROM route_baselines WHERE route = ?",
                (route,),
            ).fetchone()

            if row is None:
                # First sample on cold start
                new_ema = round(float(ar_current), 4)
                new_count = 1
                target_conn.execute(
                    "INSERT INTO route_baselines (route, ar_ema, sample_count, updated_at) VALUES (?, ?, ?, ?)",
                    (route, new_ema, new_count, now_iso),
                )
            else:
                historical_ema = float(row["ar_ema"])
                old_count = int(row["sample_count"])
                new_ema = round(alpha * float(ar_current) + (1.0 - alpha) * historical_ema, 4)
                new_count = old_count + 1
                target_conn.execute(
                    "UPDATE route_baselines SET ar_ema = ?, sample_count = ?, updated_at = ? WHERE route = ?",
                    (new_ema, new_count, now_iso, route),
                )

            target_conn.commit()

            return {
                "route": route,
                "ar_ema": new_ema,
                "sample_count": new_count,
                "updated_at": now_iso,
            }
        except Exception as exc:
            logger.error("Error updating route baseline for %s: %s", route, exc)
            try:
                target_conn.rollback()
            except Exception:
                pass
            raise


def save_baselines_batch(baselines: list[dict[str, Any]], conn: sqlite3.Connection | None = None) -> None:
    """Batch upsert route baselines into SQLite."""
    if not baselines:
        return
    with _store_lock:
        target_conn = conn if conn is not None else _get_store_conn()
        try:
            target_conn.executemany(
                "INSERT INTO route_baselines (route, ar_ema, sample_count, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(route) DO UPDATE SET ar_ema = excluded.ar_ema, sample_count = excluded.sample_count, updated_at = excluded.updated_at",
                [(b["route"], b["ar_ema"], b["sample_count"], b["updated_at"]) for b in baselines],
            )
            target_conn.commit()
        except Exception as exc:
            logger.error("Error saving baselines batch: %s", exc)
            try:
                target_conn.rollback()
            except Exception:
                pass


def list_route_baselines(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """List all persisted route baselines."""
    with _store_lock:
        target_conn = conn if conn is not None else _get_store_conn()
        try:
            rows = target_conn.execute(
                "SELECT route, ar_ema, sample_count, updated_at FROM route_baselines ORDER BY sample_count DESC, route ASC"
            ).fetchall()
            return [
                {
                    "route": str(r["route"]),
                    "ar_ema": float(r["ar_ema"]),
                    "sample_count": int(r["sample_count"]),
                    "updated_at": str(r["updated_at"]),
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("Error listing route baselines: %s", exc)
            return []


def reset_classifier_store(conn: sqlite3.Connection | None = None) -> None:
    """Clear all route baselines from persistent store (operational reset)."""
    with _store_lock:
        target_conn = conn if conn is not None else _get_store_conn()
        try:
            target_conn.execute("DELETE FROM route_baselines")
            target_conn.commit()
        except Exception as exc:
            logger.error("Error resetting route baselines: %s", exc)

