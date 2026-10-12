import json
import logging
import sqlite3

from fastapi import APIRouter

from ..contracts import (
    LedgerBlock,
    LedgerVerification,
    Overview,
    PipelineStage,
)
from ..store.db import get_connection
from ..store.ledger import verify_chain

logger = logging.getLogger("sb.api.overview")

router = APIRouter()

DECISIONS = (
    "FAST_PATH",
    "SANDBOX",
)


@router.get("/overview", response_model=Overview)
async def get_overview() -> Overview:
    try:
        from ..edge.telemetry import TelemetryTap

        await TelemetryTap.flush()
    except (sqlite3.Error, OSError, RuntimeError, ImportError):
        logger.debug("TelemetryTap flush skipped", exc_info=True)

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM demo_state WHERE key='run_id'"
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key='run_id'"
            ).fetchone()
        run_id = row["value"] if row else "RUN-PHASE1"

        counts = {decision: 0 for decision in DECISIONS}
        for result in conn.execute(
            "SELECT decision, COUNT(*) AS count FROM traffic_events GROUP BY decision"
        ).fetchall():
            dec = result["decision"]
            if dec in counts:
                counts[dec] = result["count"]
            elif dec == "SANDBOX":
                counts["SANDBOX"] += result["count"]

        total_events_row = conn.execute("SELECT COUNT(*) AS count FROM traffic_events").fetchone()
        total_events = total_events_row["count"] if total_events_row else 0

        sessions_by_class = {
            row["classification"]: row["count"]
            for row in conn.execute(
                """SELECT classification, COUNT(*) AS count
                   FROM sessions GROUP BY classification"""
            ).fetchall()
        }

        sess_stats = conn.execute(
            "SELECT COUNT(*) AS total, AVG(asset_ratio) AS avg_ar FROM sessions"
        ).fetchone()
        total_sessions = sess_stats["total"] if sess_stats else 0
        asset_ratio_avg = round(float(sess_stats["avg_ar"] or 0.0), 4) if sess_stats else 0.0

        canary_counts = {"active": 0, "exposed": 0, "observed": 0}
        for result in conn.execute(
            "SELECT status, COUNT(*) AS count FROM canaries GROUP BY status"
        ).fetchall():
            key = str(result["status"]).lower()
            if key in canary_counts:
                canary_counts[key] = result["count"]

        case_total = conn.execute("SELECT COUNT(*) AS count FROM cases").fetchone()["count"]
        case_detected = conn.execute(
            "SELECT COUNT(*) AS count FROM cases WHERE status = 'PROVENANCE_SIGNAL_DETECTED'"
        ).fetchone()["count"]
        latest_row = conn.execute(
            """SELECT case_id, run_id, created_at, status, confidence, primary_canary_id
            FROM cases ORDER BY created_at DESC, case_id DESC LIMIT 1"""
        ).fetchone()
        latest_case = dict(latest_row) if latest_row else None

    finally:
        conn.close()

    chain_info = verify_chain()
    ledger_status = str(chain_info.get("result", "VALID"))
    ledger_count = int(chain_info.get("count", 0))
    ledger_head = str(chain_info.get("head", ""))

    ladder = {
        "fast_path": counts.get("FAST_PATH", 0),
        "sandbox": counts.get("SANDBOX", 0),
        "canary_exposed": canary_counts.get("exposed", 0),
        "provenance": case_detected,
    }

    return Overview(
        run_id=run_id,
        counts=counts,
        ladder=ladder,
        sessions_by_class=sessions_by_class,
        canaries=canary_counts,
        cases={"total": case_total, "detected": case_detected},
        pipeline=[
            PipelineStage(stage="edge", status="ok"),
            PipelineStage(stage="offense", status="ok"),
            PipelineStage(stage="provenance", status="ok" if ledger_status == "VALID" else "down"),
        ],
        latest_case=latest_case,
        total_sessions=total_sessions,
        total_events=total_events,
        asset_ratio_avg=asset_ratio_avg,
        ledger_valid=ledger_status == "VALID",
        ledger_status=ledger_status,
        ledger_count=ledger_count,
        ledger_head=ledger_head,
    )


@router.get("/overview/ledger", response_model=LedgerVerification)
async def get_ledger_info() -> LedgerVerification:
    chain_info = verify_chain()
    conn = get_connection()
    blocks = []
    try:
        rows = conn.execute(
            "SELECT seq, kind, record, prev_hash, hash, ts FROM forensic_ledger ORDER BY seq DESC LIMIT 50"
        ).fetchall()
        for r in rows:
            rec_val = r["record"]
            try:
                rec_parsed = json.loads(rec_val) if isinstance(rec_val, str) else rec_val
            except (ValueError, TypeError):
                rec_parsed = {"raw": str(rec_val)}
            blocks.append(
                LedgerBlock(
                    seq=r["seq"],
                    kind=r["kind"],
                    record=rec_parsed,
                    prev_hash=r["prev_hash"],
                    hash=r["hash"],
                    ts=r["ts"],
                )
            )
    except sqlite3.Error:
        logger.warning("Failed to load ledger blocks for overview", exc_info=True)
    finally:
        conn.close()

    return LedgerVerification(
        result="VALID" if chain_info.get("result") == "VALID" else "TAMPERED",
        count=chain_info.get("count", 0),
        head=chain_info.get("head", ""),
        errors=chain_info.get("errors", []),
        blocks=blocks,
    )
