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
_baselines_cache: dict[str, dict[str, Any]] = {}
_dirty_routes: set[str] = set()
_flush_thread: threading.Thread | None = None
_flush_stop_event = threading.Event()


def _get_store_conn() -> sqlite3.Connection:
    global _store_conn
    if _store_conn is None:
        _store_conn = get_connection()
    return _store_conn


def _background_flush_loop() -> None:
    """Background worker draining and persisting dirty baselines in batches."""
    while not _flush_stop_event.wait(timeout=0.1):
        drain_classifier_store()


def _ensure_background_flusher() -> None:
    """Ensure background persist thread is active."""
    global _flush_thread
    if _flush_thread is None or not _flush_thread.is_alive():
        _flush_stop_event.clear()
        _flush_thread = threading.Thread(target=_background_flush_loop, daemon=True, name="sb-baseline-flusher")
        _flush_thread.start()


def drain_classifier_store(conn: sqlite3.Connection | None = None) -> None:
    """Drain all pending dirty baselines and commit to SQLite batch."""
    with _store_lock:
        if not _dirty_routes:
            return
        dirty_items = [_baselines_cache[r] for r in list(_dirty_routes) if r in _baselines_cache]
        _dirty_routes.clear()
    
    if dirty_items:
        save_baselines_batch(dirty_items, conn=conn)


def flush_classifier_store(conn: sqlite3.Connection | None = None) -> None:
    """Public alias to drain and commit all dirty baselines immediately."""
    drain_classifier_store(conn=conn)


def get_route_baseline(route: str, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    """Retrieve route baseline from persistent store or cache. Returns None if not present."""
    with _store_lock:
        if route in _baselines_cache:
            return dict(_baselines_cache[route])

        target_conn = conn if conn is not None else _get_store_conn()
        try:
            row = target_conn.execute(
                "SELECT route, ar_ema, sample_count, updated_at FROM route_baselines WHERE route = ?",
                (route,),
            ).fetchone()
            if not row:
                return None
            res = {
                "route": str(row["route"]),
                "ar_ema": float(row["ar_ema"]),
                "sample_count": int(row["sample_count"]),
                "updated_at": str(row["updated_at"]),
            }
            _baselines_cache[route] = res
            return dict(res)
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
    Synchronous commits are moved off the request path into background batch drain.
    """
    with _store_lock:
        _ensure_background_flusher()
        existing = _baselines_cache.get(route)
        if existing is None:
            # Check DB on cold cache
            target_conn = conn if conn is not None else _get_store_conn()
            try:
                row = target_conn.execute(
                    "SELECT ar_ema, sample_count FROM route_baselines WHERE route = ?",
                    (route,),
                ).fetchone()
                if row is not None:
                    existing = {
                        "route": route,
                        "ar_ema": float(row["ar_ema"]),
                        "sample_count": int(row["sample_count"]),
                    }
            except Exception as exc:
                logger.error("Error checking cold baseline for %s: %s", route, exc)

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if existing is None:
            # First sample on cold start
            new_ema = round(float(ar_current), 4)
            new_count = 1
        else:
            historical_ema = float(existing["ar_ema"])
            old_count = int(existing["sample_count"])
            new_ema = round(alpha * float(ar_current) + (1.0 - alpha) * historical_ema, 4)
            new_count = old_count + 1

        updated = {
            "route": route,
            "ar_ema": new_ema,
            "sample_count": new_count,
            "updated_at": now_iso,
        }
        _baselines_cache[route] = updated
        _dirty_routes.add(route)

        return dict(updated)


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
    """List all persisted and cached route baselines."""
    with _store_lock:
        target_conn = conn if conn is not None else _get_store_conn()
        items: dict[str, dict[str, Any]] = {}
        try:
            rows = target_conn.execute(
                "SELECT route, ar_ema, sample_count, updated_at FROM route_baselines ORDER BY sample_count DESC, route ASC"
            ).fetchall()
            for r in rows:
                rt = str(r["route"])
                items[rt] = {
                    "route": rt,
                    "ar_ema": float(r["ar_ema"]),
                    "sample_count": int(r["sample_count"]),
                    "updated_at": str(r["updated_at"]),
                }
        except Exception as exc:
            logger.error("Error listing route baselines: %s", exc)

        # Merge in-memory cache for dirty or recently updated routes
        for rt, b in _baselines_cache.items():
            items[rt] = dict(b)

        result = list(items.values())
        result.sort(key=lambda x: (-x["sample_count"], x["route"]))
        return result


def reset_classifier_store(conn: sqlite3.Connection | None = None) -> None:
    """Clear all route baselines from persistent store (operational reset)."""
    with _store_lock:
        _baselines_cache.clear()
        _dirty_routes.clear()
        target_conn = conn if conn is not None else _get_store_conn()
        try:
            target_conn.execute("DELETE FROM route_baselines")
            target_conn.commit()
        except Exception as exc:
            logger.error("Error resetting route baselines: %s", exc)

