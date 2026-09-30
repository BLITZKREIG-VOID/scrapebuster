"""Golden run — master plan §21 (fallback matrix) / ATK-10.

``capture()`` copies the SQLite DB (sqlite3 backup API), ``evidence/<run_id>/`` and
the scraper 3 dataset into ``data/golden/`` — only from a live run where all 7
steps passed. ``restore()`` loads them back and sets ``DemoStatus.mode = "golden"``
(dashboard banner RECORDED RUN). Live evidence is never deleted or overwritten.

    cd backend && python -m sb.demo.golden capture     # make capture-golden
    curl -X POST :8000/api/v1/demo/restore-golden      # make restore-golden
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import stat
import sys
from pathlib import Path

from sb.demo import (
    DATASETS_DIR,
    EVIDENCE_DIR,
    GOLDEN_DIR,
    RUN_LOCK,
    DemoBusy,
    db_path,
    get_state,
    set_state,
    utc_now,
)
from sb.demo.runner import get_status

MANIFEST = "golden.json"
GOLDEN_DB = "sb.db"


class GoldenError(RuntimeError):
    pass


def _backup(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(src)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def _rmtree(path: Path) -> None:
    """Remove a previous golden copy (evidence files are chmod 0444)."""

    def make_writable(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if path.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=make_writable)
        else:
            shutil.rmtree(path, onerror=make_writable)


def capture() -> dict:
    status = get_status()
    run_id = status.get("run_id")
    failed = [s["id"] for s in status.get("steps", []) if s.get("status") != "PASS"]
    if status.get("mode") != "live" or failed or len(status.get("steps", [])) != 7:
        raise GoldenError(f"capture requires a live run with all 7 steps PASS (run {run_id}, not PASS: {failed})")
    evidence = EVIDENCE_DIR / run_id
    if not evidence.is_dir():
        raise GoldenError(f"evidence directory missing: {evidence}")
    dataset = Path((get_state("demo_context") or {}).get("dataset_path") or DATASETS_DIR / f"{run_id}_scraper3.jsonl")
    if not dataset.is_file():
        raise GoldenError(f"dataset missing: {dataset}")
    ingested = DATASETS_DIR / "ingested"
    chain = EVIDENCE_DIR / "chain.json"
    if not ingested.is_dir() or not chain.is_file():
        raise GoldenError("capture requires ingested datasets and the evidence chain")

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    tmp_db = GOLDEN_DIR / (GOLDEN_DB + ".tmp")
    tmp_db.unlink(missing_ok=True)
    _backup(db_path(), tmp_db)
    os.replace(tmp_db, GOLDEN_DIR / GOLDEN_DB)

    _rmtree(GOLDEN_DIR / "evidence")
    shutil.copytree(evidence, GOLDEN_DIR / "evidence" / run_id)
    shutil.copy2(chain, GOLDEN_DIR / "evidence" / chain.name)
    _rmtree(GOLDEN_DIR / "datasets")
    (GOLDEN_DIR / "datasets").mkdir()
    shutil.copy2(dataset, GOLDEN_DIR / "datasets" / dataset.name)
    shutil.copytree(ingested, GOLDEN_DIR / "datasets" / "ingested")

    manifest = {
        "run_id": run_id,
        "captured_at": utc_now(),
        "db": GOLDEN_DB,
        "evidence": f"evidence/{run_id}",
        "dataset": f"datasets/{dataset.name}",
        "ingested": "datasets/ingested",
        "chain": "evidence/chain.json",
    }
    (GOLDEN_DIR / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def restore() -> dict:
    """Load the golden run; returns ``DemoStatus`` with ``mode: golden``. Raises DemoBusy if locked."""
    if not RUN_LOCK.acquire(blocking=False):
        raise DemoBusy("a demo run is in progress")
    try:
        manifest_path = GOLDEN_DIR / MANIFEST
        if not manifest_path.is_file():
            raise GoldenError(f"no golden run captured ({manifest_path} missing)")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_id = manifest["run_id"]

        if "ingested" not in manifest or "chain" not in manifest:
            raise GoldenError("golden snapshot lacks ingested datasets/chain; capture a complete live run")
        _backup(GOLDEN_DIR / manifest["db"], db_path())

        evidence = EVIDENCE_DIR / run_id
        if not evidence.exists():  # never overwrite or delete live evidence
            shutil.copytree(GOLDEN_DIR / manifest["evidence"], evidence)
        DATASETS_DIR.mkdir(parents=True, exist_ok=True)
        dataset = GOLDEN_DIR / manifest["dataset"]
        shutil.copy2(dataset, DATASETS_DIR / dataset.name)
        shutil.copytree(GOLDEN_DIR / manifest["ingested"], DATASETS_DIR / "ingested", dirs_exist_ok=True)
        chain = EVIDENCE_DIR / "chain.json"
        if not chain.exists():  # preserve existing live evidence and expose corruption
            shutil.copy2(GOLDEN_DIR / manifest["chain"], chain)

        status = get_status()
        status.update(run_id=run_id, mode="golden", phase="COMPLETE")
        set_state("demo_status", status)
        set_state("run_id", run_id)
        set_state("phase", "COMPLETE")
        set_state("demo_context", {**(get_state("demo_context") or {}), "dataset_path": str(DATASETS_DIR / dataset.name)})
        return status
    finally:
        RUN_LOCK.release()


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Capture / restore the golden demo run.")
    ap.add_argument("action", choices=("capture", "restore"))
    args = ap.parse_args()
    try:
        result = capture() if args.action == "capture" else restore()
    except (GoldenError, DemoBusy) as exc:
        print(f"FAIL  {args.action}-golden: {exc}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
