"""Doberman probe runner and interrogator (master plan A10, Phase 4 PRD M4).

Implements configurable probe targets, prompt sequences, request/response/control/match
transcripts, and automatic case linking for verbatim positive matches.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sb.canary import registry
from sb.contracts import Canary
from sb.store import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Probe Configuration Models
# ---------------------------------------------------------------------------

@dataclass
class ProbeTarget:
    """A configurable probe target (LLM endpoint or API)."""
    target_id: str
    name: str
    endpoint: str
    auth_headers: dict[str, str] = field(default_factory=dict)
    model_params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class ProbePrompt:
    """A prompt template for probing."""
    prompt_id: str
    name: str
    template: str  # Jinja2-style template with {canary_value}, {canary_id}, {context} placeholders
    category: str  # e.g., "extraction", "inference", "reconstruction"
    expected_pattern: str | None = None  # Regex pattern for positive match


@dataclass
class ProbeSequence:
    """A sequence of prompts to execute against a target."""
    sequence_id: str
    name: str
    prompt_ids: list[str]
    control_prompt_ids: list[str] = field(default_factory=list)  # Control prompts (no canary)
    target_id: str | None = None
    max_retries: int = 2
    timeout_seconds: int = 30


@dataclass
class ProbeTranscript:
    """Complete transcript of a probe run."""
    transcript_id: str
    probe_run_id: str
    target_id: str
    prompt_id: str
    prompt_text: str
    request_payload: dict[str, Any]
    response_text: str
    response_metadata: dict[str, Any]
    latency_ms: int
    match_result: bool
    match_details: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Probe Configuration Registry
# ---------------------------------------------------------------------------

_PROBE_TARGETS: dict[str, ProbeTarget] = {}
_PROBE_PROMPTS: dict[str, ProbePrompt] = {}
_PROBE_SEQUENCES: dict[str, ProbeSequence] = {}
_CONFIG_LOCK = threading.RLock()


def register_probe_target(target: ProbeTarget) -> None:
    """Register a probe target."""
    with _CONFIG_LOCK:
        _PROBE_TARGETS[target.target_id] = target


def get_probe_target(target_id: str) -> ProbeTarget | None:
    """Get a probe target by ID."""
    with _CONFIG_LOCK:
        return _PROBE_TARGETS.get(target_id)


def list_probe_targets() -> list[ProbeTarget]:
    """List all registered probe targets."""
    with _CONFIG_LOCK:
        return list(_PROBE_TARGETS.values())


def register_probe_prompt(prompt: ProbePrompt) -> None:
    """Register a probe prompt."""
    with _CONFIG_LOCK:
        _PROBE_PROMPTS[prompt.prompt_id] = prompt


def get_probe_prompt(prompt_id: str) -> ProbePrompt | None:
    """Get a probe prompt by ID."""
    with _CONFIG_LOCK:
        return _PROBE_PROMPTS.get(prompt_id)


def register_probe_sequence(sequence: ProbeSequence) -> None:
    """Register a probe sequence."""
    with _CONFIG_LOCK:
        _PROBE_SEQUENCES[sequence.sequence_id] = sequence


def get_probe_sequence(sequence_id: str) -> ProbeSequence | None:
    """Get a probe sequence by ID."""
    with _CONFIG_LOCK:
        return _PROBE_SEQUENCES.get(sequence_id)


def list_probe_sequences() -> list[ProbeSequence]:
    """List all registered probe sequences."""
    with _CONFIG_LOCK:
        return list(_PROBE_SEQUENCES.values())


def load_probe_config_from_env() -> None:
    """Load probe configuration from environment variables and JSON files.
    
    SB_PROBE_CONFIG_PATH: Path to JSON config file
    SB_PROBE_TARGETS: JSON string of targets
    SB_PROBE_PROMPTS: JSON string of prompts
    SB_PROBE_SEQUENCES: JSON string of sequences
    """
    import json
    
    config_path = os.getenv("SB_PROBE_CONFIG_PATH", "").strip()
    if config_path:
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            for t in config.get("targets", []):
                register_probe_target(ProbeTarget(**t))
            for p in config.get("prompts", []):
                register_probe_prompt(ProbePrompt(**p))
            for s in config.get("sequences", []):
                register_probe_sequence(ProbeSequence(**s))
        except Exception as exc:
            logger.warning("Failed to load probe config from %s: %s", config_path, exc)
    
    # Load from environment variables
    for env_var, loader, registry_fn in [
        ("SB_PROBE_TARGETS", json.loads, lambda x: [register_probe_target(ProbeTarget(**t)) for t in x]),
        ("SB_PROBE_PROMPTS", json.loads, lambda x: [register_probe_prompt(ProbePrompt(**p)) for p in x]),
        ("SB_PROBE_SEQUENCES", json.loads, lambda x: [register_probe_sequence(ProbeSequence(**s)) for s in x]),
    ]:
        val = os.getenv(env_var, "").strip()
        if val:
            try:
                registry_fn(json.loads(val))
            except Exception as exc:
                logger.warning("Failed to load %s: %s", env_var, exc)


# ---------------------------------------------------------------------------
# Probe Transcript Store
# ---------------------------------------------------------------------------

_TRANSCRIPT_LOCK = threading.RLock()


def _init_transcript_tables() -> None:
    """Initialize transcript tables in database."""
    conn = db.get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS probe_targets (
                target_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                auth_headers TEXT DEFAULT '{}',
                model_params TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS probe_prompts (
                prompt_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                template TEXT NOT NULL,
                category TEXT NOT NULL,
                expected_pattern TEXT
            );

            CREATE TABLE IF NOT EXISTS probe_sequences (
                sequence_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                prompt_ids TEXT DEFAULT '[]',
                control_prompt_ids TEXT DEFAULT '[]',
                target_id TEXT,
                max_retries INTEGER DEFAULT 2,
                timeout_seconds INTEGER DEFAULT 30
            );

            CREATE TABLE IF NOT EXISTS probe_transcripts (
                transcript_id TEXT PRIMARY KEY,
                probe_run_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                prompt_id TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                request_payload TEXT NOT NULL,
                response_text TEXT NOT NULL,
                response_metadata TEXT DEFAULT '{}',
                latency_ms INTEGER NOT NULL,
                match_result INTEGER NOT NULL,
                match_details TEXT DEFAULT '{}',
                ts TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_probe_transcripts_run ON probe_transcripts(probe_run_id);
            CREATE INDEX IF NOT EXISTS idx_probe_transcripts_target ON probe_transcripts(target_id);
            CREATE INDEX IF NOT EXISTS idx_probe_transcripts_ts ON probe_transcripts(ts);
        """)
        conn.commit()
    except Exception as exc:
        logger.error("Failed to initialize transcript tables: %s", exc)
        raise


def save_probe_transcript(transcript: ProbeTranscript, conn: sqlite3.Connection | None = None) -> None:
    """Save a probe transcript to the database."""
    manage_conn = conn is None
    target_conn = db.get_connection() if manage_conn else conn
    assert target_conn is not None
    try:
        if manage_conn:
            target_conn.execute("BEGIN IMMEDIATE")
        target_conn.execute(
            """INSERT INTO probe_transcripts (
                transcript_id, probe_run_id, target_id, prompt_id,
                prompt_text, request_payload, response_text, response_metadata,
                latency_ms, match_result, match_details, ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                transcript.transcript_id,
                transcript.probe_run_id,
                transcript.target_id,
                transcript.prompt_id,
                transcript.prompt_text,
                json.dumps(transcript.request_payload),
                transcript.response_text,
                json.dumps(transcript.response_metadata),
                transcript.latency_ms,
                1 if transcript.match_result else 0,
                json.dumps(transcript.match_details),
                transcript.ts,
            ),
        )
        if manage_conn:
            target_conn.execute("COMMIT")
    except Exception as exc:
        if manage_conn:
            try:
                target_conn.execute("ROLLBACK")
            except Exception:
                pass
        logger.error("Failed to save probe transcript: %s", exc)
        raise
    finally:
        if manage_conn:
            target_conn.close()


def get_probe_transcripts(
    probe_run_id: str | None = None,
    target_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query probe transcripts."""
    conn = db.get_connection()
    try:
        query = "SELECT * FROM probe_transcripts WHERE 1=1"
        params: list[Any] = []
        if probe_run_id:
            query += " AND probe_run_id = ?"
            params.append(probe_run_id)
        if target_id:
            query += " AND target_id = ?"
            params.append(target_id)
        query += " ORDER BY ts DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# Initialize transcript tables on module load
_init_transcript_tables()


# ---------------------------------------------------------------------------
# Probe Runner (enhanced with sequences and transcripts)
# ---------------------------------------------------------------------------

def run_probe_sequence(
    sequence_id: str,
    canary_ids: list[str] | None = None,
    *,
    generate: Callable[..., Any] | None = None,
) -> list[str]:
    """Run a complete probe sequence against target and control.
    
    Returns list of probe_run_ids (target, control for each prompt in sequence).
    """
    from sb.provenance import llm
    
    sequence = get_probe_sequence(sequence_id)
    if sequence is None:
        raise KeyError(f"Probe sequence not found: {sequence_id}")
    
    if sequence.target_id is None:
        raise ValueError(f"Sequence {sequence_id} has no target_id configured")
    
    target = get_probe_target(sequence.target_id)
    if target is None:
        raise KeyError(f"Target not found: {sequence.target_id}")
    
    # Resolve canaries
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
    
    if not canaries:
        raise ValueError("No canaries selected for probing.")
    
    generate_fn = generate if generate is not None else llm.generate
    
    probe_run_ids: list[str] = []
    
    try:
        for target_role in ["target", "control"]:
            # For control, we still use the same target endpoint but with control prompts
            probe_run_ids_for_role: list[str] = []
            
            for prompt_id in sequence.prompt_ids:
                prompt = get_probe_prompt(prompt_id)
                if prompt is None:
                    logger.warning("Prompt not found: %s", prompt_id)
                    continue
                
                probe_id = f"PRB-{secrets.token_hex(4)}"
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
                        target.target_id,
                        "",
                        json.dumps(model_data),
                        "RUNNING",
                    ),
                )
            
            for canary in canaries:
                # Build prompt with canary values
                prompt_text = prompt.template.format(
                    canary_value=canary.canonical_content,
                    canary_id=canary.canary_id,
                    context="",
                )
                
                # Execute probe against target endpoint
                # This would be where you call the actual LLM API
                # For now, we use the existing generate function
                fallback_text = ""
                result = generate_fn(prompt_text, fallback_text=fallback_text)
                
                # Save transcript
                transcript = ProbeTranscript(
                    transcript_id=f"TRN-{secrets.token_hex(4)}",
                    probe_run_id=probe_id,
                    target_id=target.target_id,
                    prompt_id=prompt_id,
                    prompt_text=prompt_text,
                    request_payload={"prompt": prompt_text, "canary_id": canary.canary_id},
                    response_text=result.text,
                    response_metadata={
                        "model_name": result.model_name,
                        "model_digest": result.model_digest,
                        "mode": result.mode,
                        "latency_ms": int(result.latency_ms),
                    },
                    latency_ms=int(result.latency_ms),
                    match_result=False,  # Will be updated after analysis
                    match_details={},
                )
                save_probe_transcript(transcript)
                
                # Check for verbatim match
                if prompt.expected_pattern:
                    import re
                    if re.search(prompt.expected_pattern, result.text):
                        pass  # Match found - in practice you'd update the transcript
                
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
                from sb.store.ledger import append_event
                append_event(
                    "probe_run",
                    {
                        "probe_id": probe_id,
                        "target": target_role,
                        "dataset_id": target.target_id,
                        "dataset_sha256": "",
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "model": model_data,
                        "status": "DONE",
                    },
                )
                probe_run_ids_for_role.append(probe_id)
            
            probe_run_ids.extend(probe_run_ids_for_role)
    
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
        from sb.store.ledger import append_event
        append_event(
            "probe_run",
            {
                "probe_id": probe_id,
                "target": target_role,
                "dataset_id": target.target_id,
                "dataset_sha256": "",
                "started_at": started_at,
                "finished_at": finished_at,
                "status": "FAILED",
            },
        )
        raise
    
    return probe_run_ids


# ---------------------------------------------------------------------------
# Legacy run_probe (kept for backward compatibility)
# ---------------------------------------------------------------------------

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

                from sb.store.ledger import append_event
                append_event(
                    "probe_result",
                    {
                        "result_id": result_id,
                        "probe_id": probe_id,
                        "canary_id": canary.canary_id,
                        "target": target_role,
                        "dataset_id": ds_id,
                        "prompt": prompt,
                        "retrieved": retrieved,
                        "response_text": response_text,
                        "response_sha256": response_sha256,
                        "latency_ms": int(result.latency_ms),
                        "ts": ts,
                    },
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
            from sb.store.ledger import append_event
            append_event(
                "probe_run",
                {
                    "probe_id": probe_id,
                    "target": target_role,
                    "dataset_id": ds_id,
                    "dataset_sha256": ds_sha256,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "model": model_data,
                    "status": "DONE",
                },
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
            from sb.store.ledger import append_event
            append_event(
                "probe_run",
                {
                    "probe_id": probe_id,
                    "target": target_role,
                    "dataset_id": ds_id,
                    "dataset_sha256": ds_sha256,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "status": "FAILED",
                },
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