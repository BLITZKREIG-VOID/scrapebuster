#!/usr/bin/env python3
"""Provenance probe stability evaluator and replay capture script (master plan §19 T-PR-3)."""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Setup repository root and backend import path
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# BEFORE importing sb.store.db: set env SB_DB_PATH to a fresh temp file so demo DB is never touched
_temp_db_fd, _temp_db_path = tempfile.mkstemp(suffix=".db", prefix="sb_stability_")
os.close(_temp_db_fd)
os.environ["SB_DB_PATH"] = _temp_db_path

from sb.canary import hashing, registry, seed
from sb.provenance import dataset, doberman, llm
from sb.store import db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PRV-07 probe stability script and replay capture."
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Path to target scraped dataset JSONL.",
    )
    parser.add_argument(
        "--control",
        type=Path,
        default=REPO_ROOT / "data" / "control" / "control_clean.jsonl",
        help="Path to control dataset JSONL (default: data/control/control_clean.jsonl).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of probe runs (default: 10).",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=9,
        help="Threshold of exact matches to pass stability (default: 9).",
    )
    parser.add_argument(
        "--replay-dir",
        type=Path,
        default=REPO_ROOT / "data" / "replay",
        help="Directory for golden replay output (default: data/replay).",
    )
    parser.add_argument(
        "--no-replay",
        action="store_true",
        help="Disable saving golden replay file.",
    )

    args = parser.parse_args(argv)

    # 1. Target resolution
    target_path: Path | None = args.target
    if target_path is None:
        matching = sorted(glob.glob(str(REPO_ROOT / "data" / "datasets" / "*_scraper3.jsonl")))
        if len(matching) == 0:
            sys.stderr.write(
                "Error: --target not specified and zero files match data/datasets/*_scraper3.jsonl\n"
            )
            sys.exit(2)
        elif len(matching) > 1:
            sys.stderr.write(
                f"Error: --target not specified and multiple ({len(matching)}) files match data/datasets/*_scraper3.jsonl: {matching}\n"
            )
            sys.exit(2)
        target_path = Path(matching[0])
    else:
        if not target_path.is_file():
            sys.stderr.write(f"Error: Target dataset file not found: {target_path}\n")
            sys.exit(2)

    # 2. Control file validation
    control_path: Path = args.control
    if not control_path.is_file():
        sys.stderr.write(
            f"Error: Control dataset not found at {control_path}. Please run scripts/build_control_dataset.py to generate it.\n"
        )
        sys.exit(2)

    # 3. Preflight check for live Ollama LLM
    minfo = llm.model_info()
    status = llm.llm_status()
    if status != "ok":
        sys.stderr.write(
            f"LLM status: {status} (model info: {minfo})\n"
        )
        sys.exit(3)

    # 4. DB and Ingest setup with temporary directories
    temp_ingest_dir_obj = tempfile.TemporaryDirectory(prefix="sb_ingested_")
    try:
        dataset.INGEST_DIR = Path(temp_ingest_dir_obj.name)
        db.reset_db()
        seed.seed_canaries()

        target_ds = dataset.ingest(target_path, role="target")
        control_ds = dataset.ingest(control_path, role="control")

        canaries = registry.list_canaries()
        all_canary_ids = [c.canary_id for c in canaries]

        exact_matches = {cid: 0 for cid in all_canary_ids}
        control_positives = {cid: 0 for cid in all_canary_ids}
        modes_seen = {cid: set() for cid in all_canary_ids}

        runs_count = args.runs
        threshold = args.threshold

        run_live_flags: list[bool] = []
        first_live_run_payload: dict | None = None

        for run_idx in range(1, runs_count + 1):
            t_probe_id, c_probe_id = doberman.run_probe(
                target_ds.dataset_id, control_ds.dataset_id, canary_ids=all_canary_ids
            )
            t_probe = doberman.get_probe(t_probe_id)
            c_probe = doberman.get_probe(c_probe_id)

            if t_probe is None or c_probe is None:
                sys.stderr.write(f"Error: Failed to retrieve probe results for run {run_idx}\n")
                sys.exit(1)

            t_results_map = {r["canary_id"]: r for r in t_probe["results"]}
            c_results_map = {r["canary_id"]: r for r in c_probe["results"]}

            t_modes = t_probe["model"].get("modes", {})
            c_modes = c_probe["model"].get("modes", {})

            run_is_live = True
            for cid in all_canary_ids:
                tm = t_modes.get(cid, "unknown")
                cm = c_modes.get(cid, "unknown")
                modes_seen[cid].add(tm)
                modes_seen[cid].add(cm)
                if tm != "live" or cm != "live":
                    run_is_live = False

            if not run_is_live:
                sys.stderr.write(f"Run {run_idx}/{runs_count}: Marked invalid due to non-live model mode.\n")

            run_live_flags.append(run_is_live)

            # Evaluate matches and false positives
            for canary in canaries:
                cid = canary.canary_id
                anchor_norm = hashing.normalize_for_match(canary.anchor)

                t_res = t_results_map.get(cid, {})
                t_resp_text = t_res.get("response_text", "")
                if anchor_norm in hashing.normalize_for_match(t_resp_text):
                    exact_matches[cid] += 1

                c_res = c_results_map.get(cid, {})
                c_resp_text = c_res.get("response_text", "")
                if anchor_norm in hashing.normalize_for_match(c_resp_text):
                    control_positives[cid] += 1

            # Save payload of the FIRST fully live run for replay
            if run_is_live and first_live_run_payload is None:
                t_responses = {
                    cid: {
                        "prompt": t_results_map[cid]["prompt"],
                        "response_text": t_results_map[cid]["response_text"],
                        "response_sha256": t_results_map[cid]["response_sha256"],
                    }
                    for cid in all_canary_ids
                }
                c_responses = {
                    cid: {
                        "prompt": c_results_map[cid]["prompt"],
                        "response_text": c_results_map[cid]["response_text"],
                        "response_sha256": c_results_map[cid]["response_sha256"],
                    }
                    for cid in all_canary_ids
                }

                captured_at = t_probe.get("started_at") or registry.now_iso()
                first_live_run_payload = {
                    "captured_at": captured_at,
                    "model": {
                        "name": t_probe["model"].get("name"),
                        "digest": t_probe["model"].get("digest"),
                    },
                    "options": llm.OPTIONS,
                    "target_dataset_sha256": target_ds.sha256,
                    "control_dataset_sha256": control_ds.sha256,
                    "responses": {
                        "target": t_responses,
                        "control": c_responses,
                    },
                }

        # Print stability summary table
        print(f"\nProbe Stability Results ({runs_count} runs):")
        header = f"{'Canary ID':<12} | {'Anchor':<35} | {'Exact Matches':<13} | {'Control Pos':<11} | {'Modes Seen'}"
        print(header)
        print("-" * len(header))
        for canary in canaries:
            cid = canary.canary_id
            anchor_disp = canary.anchor if len(canary.anchor) <= 35 else canary.anchor[:32] + "..."
            matches_str = f"{exact_matches[cid]}/{runs_count}"
            ctrl_str = f"{control_positives[cid]}/{runs_count}"
            modes_str = ", ".join(sorted(modes_seen[cid]))
            print(f"{cid:<12} | {anchor_disp:<35} | {matches_str:<13} | {ctrl_str:<11} | {modes_str}")

        passing_ids = [c.canary_id for c in canaries if exact_matches[c.canary_id] >= threshold]
        failing_canaries = [c for c in canaries if exact_matches[c.canary_id] < threshold]

        passing_str = ",".join(sorted(passing_ids))
        for c in failing_canaries:
            print(f"exclude via SB_PROBE_CANARIES={passing_str}")

        # Handle replay file saving
        if not args.no_replay:
            if first_live_run_payload is not None:
                replay_dir: Path = args.replay_dir
                replay_dir.mkdir(parents=True, exist_ok=True)
                utc_now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                replay_file = replay_dir / f"replay_{utc_now_str}.json"
                replay_file.write_text(json.dumps(first_live_run_payload, indent=2), encoding="utf-8")
                print(f"\nSaved golden replay file to {replay_file}")
            else:
                print("\nNo fully live run observed; replay file was not saved.")

        all_canaries_passed = len(failing_canaries) == 0
        all_runs_live = all(run_live_flags)

        if all_canaries_passed and all_runs_live:
            return 0
        else:
            return 1

    finally:
        temp_ingest_dir_obj.cleanup()
        if os.path.exists(_temp_db_path):
            try:
                os.remove(_temp_db_path)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
