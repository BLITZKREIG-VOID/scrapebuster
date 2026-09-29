"""RESET DEMO — master plan §21, steps 1–8. ``make reset`` / ``POST /api/v1/demo/reset``."""
from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx

from sb.demo import (
    DATASETS_DIR,
    OLLAMA_URL,
    ORIGIN_URL,
    RUN_LOCK,
    DemoBusy,
    MissingDependency,
    connect,
    get_state,
    require,
    set_state,
)
from sb.demo.runner import fresh_status

# §21 step 4: provenance must register its reset through sb.hooks.register_reset_hook.
PROVENANCE_OWNER = "PRV-01 Hardik"
# §21 step 8: tables that must be empty after reset (§15 schema).
ZERO_TABLES = (
    "traffic_events", "sessions", "trap_hits", "exposures", "datasets",
    "probe_runs", "probe_results", "cases", "evidence_objects",
)
EXPECTED_CANARIES = 5


def reset_demo() -> dict:
    """Run the §21 reset. Raises :class:`DemoBusy` if a demo run holds the run lock."""
    if not RUN_LOCK.acquire(blocking=False):
        raise DemoBusy("a demo run is in progress")
    try:
        return _reset()
    finally:
        RUN_LOCK.release()


def _reset() -> dict:
    checks: list[dict] = []

    def run(name: str, fn: Callable[[], object]) -> None:
        try:
            detail = fn()
            checks.append({"name": name, "ok": True, "detail": "" if detail is None else str(detail)})
        except Exception as exc:  # every failure is reported by name, never skipped
            checks.append({"name": name, "ok": False, "detail": f"{exc.__class__.__name__}: {exc}"})

    previous_run = get_state("run_id")

    # 2. drop / recreate all tables
    run("store.reset_db", lambda: require("sb.store.db", "reset_db", "INT-03 Anirudh")())

    # 3. edge in-memory sessions (INT-04)
    run("reset_hook.edge", lambda: require("sb.edge.session", "sessions", "INT-04 Anirudh").reset())

    # 4. trap hooks + every hook registered via sb.hooks.register_reset_hook (provenance, ...)
    run("reset_hook.trap", _reset_trap)
    run("reset_hook.registry", lambda: require("sb.hooks", "run_reset_hooks", "INT-04 Anirudh")())
    run("reset_hook.provenance", _check_provenance_registered)

    # 5. runtime datasets only; evidence/ is never touched
    run("datasets.cleared", _clear_datasets)

    # 6. new run id, phase READY, fresh demo status
    run_id = _new_run_id(previous_run)
    run("demo_state.run_id", lambda: _write_state(run_id))

    # 7. seed the five canaries (+ publication records)
    run("canary.seed", lambda: require("sb.canary.seed", "seed_canaries", "CAN-01 Hardik")())

    # 8. self-check
    run("self_check.counts_zero", _check_counts_zero)
    run("self_check.canaries_active", _check_canaries_active)
    run("self_check.origin_reachable", _check_origin)
    checks.append({"name": "self_check.llm_reported", "ok": True, "detail": _llm_status()})

    return {"ok": all(c["ok"] for c in checks), "run_id": run_id, "checks": checks}


def _clear_datasets() -> str:
    removed = 0
    for path in DATASETS_DIR.glob("*.jsonl"):
        path.unlink()
        removed += 1
    ingested = DATASETS_DIR / "ingested"
    if ingested.is_dir():
        for path in ingested.iterdir():
            shutil.rmtree(path) if path.is_dir() else path.unlink()
            removed += 1
    return f"{removed} removed"


def _reset_trap() -> str:
    trap_hooks = require("sb.hooks", "trap_hooks", "INT-04 Anirudh")
    if type(trap_hooks).__name__ == "NoOpTrapHooks":
        raise MissingDependency("sb.hooks.trap_hooks is still NoOpTrapHooks (TRP-01/TRP-02 Hardik)")
    trap_hooks.reset()
    return type(trap_hooks).__name__


def _check_provenance_registered() -> str:
    registry = require("sb.hooks", "_reset_hooks", "INT-04 Anirudh")
    owners = sorted({getattr(hook, "__module__", "") or "" for hook in registry})
    if not any(owner.startswith("sb.provenance") for owner in owners):
        raise MissingDependency(
            f"no sb.provenance reset hook registered via sb.hooks.register_reset_hook "
            f"({PROVENANCE_OWNER}); registered: {owners or 'none'}"
        )
    return ", ".join(owners)


def _new_run_id(previous: str | None) -> str:
    """``RUN-YYYYMMDD-HHMMSS`` (UTC); never equal to the previous run id."""
    while True:
        run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%d-%H%M%S")
        if run_id != previous:
            return run_id
        time.sleep(0.05)


def _write_state(run_id: str) -> str:
    set_state("run_id", run_id)
    set_state("phase", "READY")
    set_state("demo_status", fresh_status(run_id))
    set_state("demo_context", {})
    return run_id


def _check_counts_zero() -> str:
    problems = []
    with connect() as conn:
        for table in ZERO_TABLES:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception as exc:
                problems.append(f"{table}: {exc}")
                continue
            if count:
                problems.append(f"{table}={count}")
    if problems:
        raise AssertionError(", ".join(problems))
    return "all zero: " + ", ".join(ZERO_TABLES)


def _check_canaries_active() -> str:
    with connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) FROM canaries GROUP BY status").fetchall()
    counts = {status: n for status, n in rows}
    if counts != {"ACTIVE": EXPECTED_CANARIES}:
        raise AssertionError(f"expected {{'ACTIVE': {EXPECTED_CANARIES}}}, got {counts}")
    return f"{EXPECTED_CANARIES} ACTIVE"


def _check_origin() -> str:
    resp = httpx.get(ORIGIN_URL + "/", timeout=5)
    if resp.status_code != 200:
        raise AssertionError(f"{ORIGIN_URL}/ -> {resp.status_code}")
    return f"{ORIGIN_URL} 200"


def _llm_status() -> str:
    """Reported, not gated: the probe falls back to extractive mode when Ollama is down."""
    try:
        resp = httpx.get(OLLAMA_URL + "/api/tags", timeout=3)
        return "ok" if resp.status_code == 200 else f"down (HTTP {resp.status_code})"
    except httpx.HTTPError as exc:
        return f"down ({exc.__class__.__name__})"
