"""Provenance investigation pipeline (PRV-06)."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sb.canary import registry
from sb.contracts import Case, CaseSummary, Finding
from sb.provenance import correlate, dataset, doberman, evidence, llm, vault_s3
from sb.store import db

GENERATE_FN: Callable[..., Any] | None = None

SESSION_JSON_COLUMNS: tuple[str, ...] = (
    "l1_reasons",
    "l2_signals",
    "layer_path",
    "pages",
    "traps_triggered",
    "canaries_exposed",
)


def current_run_id() -> str:
    """Read demo_state row key 'run_id'; if absent, create RUN-YYYYMMDD-HHMMSS (UTC now),
    INSERT OR IGNORE it into demo_state, and return it.
    """
    with closing(db.get_connection()) as conn, conn:
        row = conn.execute("SELECT value FROM demo_state WHERE key = 'run_id'").fetchone()
        if row is not None and row["value"]:
            return str(row["value"])

        new_run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%d-%H%M%S")
        conn.execute(
            "INSERT OR IGNORE INTO demo_state (key, value) VALUES ('run_id', ?)",
            (new_run_id,),
        )
        row = conn.execute("SELECT value FROM demo_state WHERE key = 'run_id'").fetchone()
        return str(row["value"])


def _load_baseline_texts(baseline_path: Path | str | None = None) -> list[str]:
    b_path = (
        Path(baseline_path)
        if baseline_path is not None
        else Path(__file__).resolve().parents[3] / "data" / "baseline" / "public_baseline.jsonl"
    )
    if not b_path.is_file():
        return []
    texts: list[str] = []
    with b_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if not isinstance(rec, dict) or "text" not in rec or not isinstance(rec["text"], str):
                raise ValueError(f"Invalid baseline record at line {line_no}: missing str 'text'")
            texts.append(rec["text"])
    return texts


def investigate(
    target_dataset_id: str | None = None,
    control_dataset_id: str | None = None,
    canary_ids: list[str] | None = None,
    *,
    generate: Callable[..., Any] | None = None,
    baseline_path: Path | None = None,
) -> dict[str, Any]:
    """Execute end-to-end provenance investigation: run probes, correlate signals,
    build evidence bundle, and transition detected canaries.
    """
    # 1. Resolve target dataset
    if target_dataset_id is None:
        target_ds = dataset.latest("target")
        if target_ds is None:
            raise ValueError("no target dataset ingested")
        target_dataset_id = target_ds.dataset_id
    else:
        target_ds = dataset.get_dataset(target_dataset_id)
        if target_ds is None:
            raise KeyError(f"Target dataset not found: {target_dataset_id}")

    # 2. Resolve control dataset
    if control_dataset_id is None:
        control_ds = dataset.latest("control")
        if control_ds is None:
            raise ValueError("no control dataset ingested")
        control_dataset_id = control_ds.dataset_id
    else:
        control_ds = dataset.get_dataset(control_dataset_id)
        if control_ds is None:
            raise KeyError(f"Control dataset not found: {control_dataset_id}")

    gen_fn = generate if generate is not None else GENERATE_FN

    # 3. Run probes
    target_probe_id, control_probe_id = doberman.run_probe(
        target_dataset_id=target_dataset_id,
        control_dataset_id=control_dataset_id,
        canary_ids=canary_ids,
        generate=gen_fn,
    )

    probe_ids = {"target": target_probe_id, "control": control_probe_id}

    target_probe = doberman.get_probe(target_probe_id)
    control_probe = doberman.get_probe(control_probe_id)
    if target_probe is None or control_probe is None:
        raise RuntimeError("Failed to retrieve completed probe runs.")

    target_results_by_canary = {r["canary_id"]: r for r in target_probe["results"]}
    control_results_by_canary = {r["canary_id"]: r for r in control_probe["results"]}

    probed_canary_ids = [r["canary_id"] for r in target_probe["results"]]
    probed_canaries = [
        c
        for cid in probed_canary_ids
        if (c := registry.get(cid)) is not None
    ]

    # 4. Load control and baseline texts
    control_records = dataset.load_records(control_dataset_id)
    control_texts = [
        r["text"]
        for r in control_records
        if isinstance(r, dict) and "text" in r and isinstance(r["text"], str)
    ]
    baseline_texts = _load_baseline_texts(baseline_path)

    # 5. Build correlate inputs
    run_id = current_run_id()
    with closing(db.get_connection()) as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM cases WHERE run_id = ?", (run_id,)).fetchone()
        case_count = row["cnt"] if row else 0
    case_n = 1 + case_count
    case_id = f"SB-{case_n:03d}"

    inputs: list[dict[str, Any]] = []
    exposures_by_cid: dict[str, list[dict[str, Any]]] = {}

    for c in probed_canaries:
        cid = c.canary_id
        pub = registry.get_publication(cid)
        exps = [exp.model_dump() for exp in registry.list_exposures(cid)]
        exposures_by_cid[cid] = exps

        t_res = target_results_by_canary.get(cid, {})
        c_res = control_results_by_canary.get(cid, {})

        t_resp_text = t_res.get("response_text", "")
        c_resp_text = c_res.get("response_text", "")
        observed_at = t_res.get("ts")

        inputs.append({
            "canary": c.model_dump(),
            "publication": pub,
            "exposures": exps,
            "target_response": t_resp_text,
            "control_response": c_resp_text,
            "ingested_at": target_ds.ingested_at,
            "observed_at": observed_at,
            "control_texts": control_texts,
            "baseline_texts": baseline_texts,
        })

    findings: list[Finding] = correlate.evaluate(case_id, inputs)
    status, confidence = correlate.case_status(findings)

    # 6. If NO_SIGNAL, create no case
    if status == "NO_SIGNAL":
        return {"probe_ids": probe_ids, "case_id": None}

    # 7. Identify primary canary and session IDs
    max_rank = max(correlate.STATUS_RANK.get(f.status, 0) for f in findings)
    primary_finding = next(
        f for f in findings if correlate.STATUS_RANK.get(f.status, 0) == max_rank
    )
    primary_canary_id = primary_finding.canary_id

    session_ids_set: set[str] = set()
    for f in findings:
        if f.status != "NO_SIGNAL":
            for exp in exposures_by_cid.get(f.canary_id, []):
                sid = exp.get("session_id")
                if sid:
                    session_ids_set.add(str(sid))
    session_ids = sorted(session_ids_set)

    # 8. Build statement
    primary_pub = registry.get_publication(primary_canary_id)
    primary_published_at = primary_pub.get("published_at") if primary_pub else None
    first_session_id = session_ids[0] if session_ids else None
    primary_exps = exposures_by_cid.get(primary_canary_id, [])
    primary_first_exp_ts = primary_exps[0].get("ts") if primary_exps else None
    primary_observed_at = primary_finding.temporal.get("observed_at")

    statement = correlate.build_statement({
        "published_at": primary_published_at,
        "session_id": first_session_id,
        "classified_at": primary_first_exp_ts,
        "observed_at": primary_observed_at,
    })

    created_at = registry.now_iso()

    # 9. Insert case row
    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            """
            INSERT INTO cases (
                case_id, run_id, created_at, status, confidence,
                primary_canary_id, session_ids, probe_ids, findings,
                evidence, statement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                run_id,
                created_at,
                status,
                confidence,
                primary_canary_id,
                json.dumps(session_ids),
                json.dumps([target_probe_id, control_probe_id]),
                json.dumps([f.model_dump() for f in findings]),
                json.dumps({}),
                statement,
            ),
        )

    # 10. Gather bundle data
    publications: list[dict[str, Any]] = [
        pub
        for c in probed_canaries
        if (pub := registry.get_publication(c.canary_id)) is not None
    ]
    all_exposures: list[dict[str, Any]] = [
        exp
        for c in probed_canaries
        for exp in exposures_by_cid.get(c.canary_id, [])
    ]

    sessions_data: list[dict[str, Any]] = []
    with closing(db.get_connection()) as conn:
        for sid in session_ids:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (sid,)).fetchone()
            if row is None:
                sessions_data.append({"session_id": sid, "profile": "unavailable"})
            else:
                s_dict = dict(row)
                for col in SESSION_JSON_COLUMNS:
                    val = s_dict.get(col)
                    if isinstance(val, str):
                        s_dict[col] = json.loads(val)
                sessions_data.append(s_dict)

    probe_request: dict[str, Any] = {
        "prompts": {
            r["canary_id"]: r["prompt"]
            for r in target_probe["results"]
        },
        "model": target_probe["model"],
        "options": llm.OPTIONS,
        "datasets": {
            "target": {
                "dataset_id": target_ds.dataset_id,
                "sha256": target_ds.sha256,
            },
            "control": {
                "dataset_id": control_ds.dataset_id,
                "sha256": control_ds.sha256,
            },
        },
        "retrieved": {
            "target": {
                r["canary_id"]: r["retrieved"]
                for r in target_probe["results"]
            },
            "control": {
                r["canary_id"]: r["retrieved"]
                for r in control_probe["results"]
            },
        },
    }

    target_modes = target_probe["model"].get("modes", {})
    target_default_mode = target_probe["model"].get("mode", "live")
    target_responses = [
        {
            "canary_id": r["canary_id"],
            "response_text": r["response_text"],
            "response_sha256": r["response_sha256"],
            "mode": target_modes.get(r["canary_id"], target_default_mode),
        }
        for r in target_probe["results"]
    ]

    control_modes = control_probe["model"].get("modes", {})
    control_default_mode = control_probe["model"].get("mode", "live")
    control_responses = [
        {
            "canary_id": r["canary_id"],
            "response_text": r["response_text"],
            "response_sha256": r["response_sha256"],
            "mode": control_modes.get(r["canary_id"], control_default_mode),
        }
        for r in control_probe["results"]
    ]

    match_analysis = [f.model_dump() for f in findings]

    case_payload = {
        "case_id": case_id,
        "run_id": run_id,
        "created_at": created_at,
        "status": status,
        "confidence": confidence,
        "primary_canary_id": primary_canary_id,
        "session_ids": session_ids,
        "probe_ids": [target_probe_id, control_probe_id],
        "findings": [f.model_dump() for f in findings],
        "statement": statement,
        "bundle": {
            "canaries": [c.model_dump() for c in probed_canaries],
            "publications": publications,
            "exposures": all_exposures,
            "sessions": sessions_data,
            "probe_request": probe_request,
            "target_responses": target_responses,
            "control_responses": control_responses,
            "match_analysis": match_analysis,
        },
    }

    # 11. Build evidence bundle (local, hash-chained), then best-effort S3 Object Lock upload
    evidence_summary = evidence.build_bundle(case_payload)
    vault_s3.preserve_async(case_id, case_payload["run_id"], evidence_summary["local_path"])

    # 12. Transition DETECTED and exact_match canaries from EXPOSED to OBSERVED
    for f in findings:
        if f.status == "PROVENANCE_SIGNAL_DETECTED" and f.exact_match:
            c = registry.get(f.canary_id)
            if c is not None and c.status == "EXPOSED":
                registry.set_status(f.canary_id, "OBSERVED")

    return {"probe_ids": probe_ids, "case_id": case_id}


def get_case(case_id: str) -> Case | None:
    """Retrieve case details by case_id, decoding JSON columns."""
    with closing(db.get_connection()) as conn:
        row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        for field in ("session_ids", "probe_ids", "findings", "evidence"):
            val = d.get(field)
            if isinstance(val, str):
                d[field] = json.loads(val)
        return Case.model_validate(d)


def list_cases() -> list[CaseSummary]:
    """List all cases ordered by created_at descending."""
    with closing(db.get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT case_id, run_id, created_at, status, confidence, primary_canary_id
            FROM cases
            ORDER BY created_at DESC, case_id DESC
            """
        ).fetchall()
        return [
            CaseSummary(
                case_id=r["case_id"],
                run_id=r["run_id"],
                created_at=r["created_at"],
                status=r["status"],
                confidence=r["confidence"],
                primary_canary_id=r["primary_canary_id"],
            )
            for r in rows
        ]
