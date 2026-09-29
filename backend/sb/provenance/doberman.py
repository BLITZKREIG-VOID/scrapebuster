"""Doberman probe runner and interrogator (master plan §10)."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
import secrets
import sqlite3
from typing import Any, Callable

from sb.canary import registry
from sb.contracts import Canary
from sb.store import db


def select_canaries(canary_ids: list[str] | None = None) -> list[Canary]:
    """Select canaries to probe according to priority rules:

    1. Explicit canary_ids if provided (unknown ID raises KeyError).
    2. Else all EXPOSED canaries in registry.
    3. Else all ACTIVE canaries in registry.
    4. If SB_PROBE_CANARIES environment variable is non-empty, keep only IDs in that comma-separated list.
    5. Returned list is ordered by canary_id ascending.
    """
    if canary_ids is not None:
        canaries: list[Canary] = []
        for cid in canary_ids:
            c = registry.get(cid)
            if c is None:
                raise KeyError(f"Unknown canary: {cid}")
            canaries.append(c)
    else:
        all_c = registry.list_canaries()
        exposed = [c for c in all_c if c.status == "EXPOSED"]
        if exposed:
            canaries = exposed
        else:
            canaries = [c for c in all_c if c.status == "ACTIVE"]

    env_canaries = os.getenv("SB_PROBE_CANARIES", "").strip()
    if env_canaries:
        allowed = {item.strip() for item in env_canaries.split(",") if item.strip()}
        canaries = [c for c in canaries if c.canary_id in allowed]

    unique_by_id = {c.canary_id: c for c in canaries}
    return sorted(unique_by_id.values(), key=lambda c: c.canary_id)


def run_probe(
    target_dataset_id: str,
    control_dataset_id: str,
    canary_ids: list[str] | None = None,
    *,
    generate: Callable[..., Any] | None = None,
) -> tuple[str, str]:
    """Run provenance probe on target and control datasets.

    Returns (probe_id_target, probe_id_control).
    """
    from sb.provenance import dataset, llm, rag

    # Unknown dataset id -> KeyError before any row is written
    target_ds = dataset.get_dataset(target_dataset_id)
    if target_ds is None:
        raise KeyError(f"Target dataset not found: {target_dataset_id}")

    control_ds = dataset.get_dataset(control_dataset_id)
    if control_ds is None:
        raise KeyError(f"Control dataset not found: {control_dataset_id}")

    # No canaries selected -> ValueError
    canaries = select_canaries(canary_ids)
    if not canaries:
        raise ValueError("No canaries selected for probing.")

    generate_fn = generate if generate is not None else llm.generate

    datasets_to_run = [
        ("target", target_dataset_id, target_ds.sha256),
        ("control", control_dataset_id, control_ds.sha256),
    ]

    probe_ids: list[str] = []

    for target_role, ds_id, ds_sha256 in datasets_to_run:
        probe_id = f"PRB-{secrets.token_hex(4)}"
        probe_ids.append(probe_id)
        started_at = registry.now_iso()

        minfo = llm.model_info()
        model_data: dict[str, Any] = {
            "name": minfo.get("name"),
            "digest": minfo.get("digest"),
            "mode": None,
            "options": llm.OPTIONS,
        }

        with closing(db.get_connection()) as conn, conn:
            conn.execute(
                """
                INSERT INTO probe_runs (
                    probe_id, started_at, finished_at, target,
                    dataset_id, dataset_sha256, model, status
                ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    probe_id,
                    started_at,
                    target_role,
                    ds_id,
                    ds_sha256,
                    json.dumps(model_data),
                    "RUNNING",
                ),
            )

        try:
            canary_results: list[tuple[Canary, Any]] = []
            for canary in canaries:
                question = canary.probe_prompts[0]
                hits = rag.retrieve(ds_id, question, k=3)
                chunks = [h[2] for h in hits]
                prompt = llm.build_prompt(chunks, question)
                fallback_text = hits[0][2] if hits else ""

                result = generate_fn(prompt, fallback_text=fallback_text)
                canary_results.append((canary, result))

                retrieved = [{"chunk_id": h[0], "score": h[1]} for h in hits]
                response_text = result.text
                response_sha256 = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
                result_id = f"RES-{secrets.token_hex(4)}"
                ts = registry.now_iso()

                with closing(db.get_connection()) as conn, conn:
                    conn.execute(
                        """
                        INSERT INTO probe_results (
                            result_id, probe_id, canary_id, prompt,
                            retrieved, response_text, response_sha256,
                            latency_ms, ts
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            result_id,
                            probe_id,
                            canary.canary_id,
                            prompt,
                            json.dumps(retrieved),
                            response_text,
                            response_sha256,
                            int(result.latency_ms),
                            ts,
                        ),
                    )

            # After all canaries:
            # model.mode = the single mode if all results share it, else "mixed";
            # add "modes": {canary_id: mode};
            # model name/digest from the first LLMResult; status "DONE", finished_at now.
            modes = {c.canary_id: res.mode for c, res in canary_results}
            unique_modes = set(modes.values())
            single_mode = next(iter(unique_modes)) if len(unique_modes) == 1 else "mixed"
            model_data["mode"] = single_mode
            model_data["modes"] = modes
            if canary_results:
                first_res = canary_results[0][1]
                model_data["name"] = first_res.model_name
                model_data["digest"] = first_res.model_digest

            finished_at = registry.now_iso()
            with closing(db.get_connection()) as conn, conn:
                conn.execute(
                    """
                    UPDATE probe_runs
                    SET finished_at = ?, model = ?, status = ?
                    WHERE probe_id = ?
                    """,
                    (finished_at, json.dumps(model_data), "DONE", probe_id),
                )

        except Exception:
            finished_at = registry.now_iso()
            with closing(db.get_connection()) as conn, conn:
                conn.execute(
                    """
                    UPDATE probe_runs
                    SET finished_at = ?, status = ?
                    WHERE probe_id = ?
                    """,
                    (finished_at, "FAILED", probe_id),
                )
            raise

    return (probe_ids[0], probe_ids[1])


def get_probe(probe_id: str) -> dict | None:
    """Retrieve a probe run and its results by probe_id, or None if not found."""
    with closing(db.get_connection()) as conn:
        run_row = conn.execute(
            """
            SELECT probe_id, target, status, dataset_id, dataset_sha256,
                   started_at, finished_at, model
            FROM probe_runs
            WHERE probe_id = ?
            """,
            (probe_id,),
        ).fetchone()

        if run_row is None:
            return None

        model_dict = json.loads(run_row["model"])

        results_rows = conn.execute(
            """
            SELECT result_id, canary_id, prompt, retrieved,
                   response_text, response_sha256, latency_ms, ts
            FROM probe_results
            WHERE probe_id = ?
            ORDER BY canary_id ASC
            """,
            (probe_id,),
        ).fetchall()

        results: list[dict[str, Any]] = []
        for r in results_rows:
            retrieved_list = json.loads(r["retrieved"])
            results.append({
                "result_id": r["result_id"],
                "canary_id": r["canary_id"],
                "prompt": r["prompt"],
                "retrieved": retrieved_list,
                "response_text": r["response_text"],
                "response_sha256": r["response_sha256"],
                "latency_ms": r["latency_ms"],
                "ts": r["ts"],
            })

        return {
            "probe_id": run_row["probe_id"],
            "target": run_row["target"],
            "status": run_row["status"],
            "dataset_id": run_row["dataset_id"],
            "dataset_sha256": run_row["dataset_sha256"],
            "started_at": run_row["started_at"],
            "finished_at": run_row["finished_at"],
            "model": model_dict,
            "results": results,
        }


def list_probes() -> list[dict]:
    """List all probe runs in the same shape as get_probe, ordered by started_at descending."""
    with closing(db.get_connection()) as conn:
        rows = conn.execute("SELECT probe_id, started_at FROM probe_runs").fetchall()

    if not rows:
        return []

    def _parse_ts(row: sqlite3.Row) -> datetime:
        return datetime.fromisoformat(row["started_at"])

    sorted_rows = sorted(rows, key=_parse_ts, reverse=True)
    probes: list[dict] = []
    for r in sorted_rows:
        probe = get_probe(r["probe_id"])
        if probe is not None:
            probes.append(probe)
    return probes
