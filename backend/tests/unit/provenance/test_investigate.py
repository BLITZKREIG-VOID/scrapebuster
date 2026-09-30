"""Unit tests for provenance investigation pipeline (PRV-06)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sb.canary import registry
from sb.canary.seed import seed_canaries
from sb.provenance import dataset, evidence, investigate, llm
from sb.provenance.llm import LLMResult
from sb.store import db


def _create_control_file(sample_path: Path, dest_path: Path) -> Path:
    """Create a control dataset JSONL file from the sample by stripping every canary paragraph."""
    canaries = registry.load_definitions()
    anchors = [c["anchor"] for c in canaries]

    records: list[dict] = []
    with sample_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            paragraphs = rec["text"].split("\n\n")
            filtered = [
                p for p in paragraphs
                if not any(anchor in p for anchor in anchors)
            ]
            rec["text"] = "\n\n".join(filtered)
            records.append(rec)

    with dest_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    return dest_path


def test_investigate_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_path: Path):
    # 1. Setup paths and monkeypatching
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr(
        llm,
        "model_info",
        lambda: {"name": "qwen2.5:3b", "digest": "sha256:testdigest123"},
    )

    def stub_generate(prompt: str, fallback_text: str = "", replay_text: str | None = None) -> LLMResult:
        return LLMResult(
            text=fallback_text,
            mode="live",
            model_name="qwen2.5:3b",
            model_digest="sha256:testdigest123",
            latency_ms=10,
        )

    # 2. Seed canaries (t0)
    seed_canaries(now="2026-01-01T10:00:00.000000Z")

    # 3. Record one exposure per canary (t1: after seeding, before ingest)
    session = SimpleNamespace(
        session_id="sb-test",
        client_key="ck-test-1",
        classification="SOPHISTICATED_SCRAPER",
    )
    ctx = SimpleNamespace(
        ip="127.0.0.1",
        user_agent="curl/8.0",
        method="GET",
        path="/docs",
        headers={"referer": "https://example.com", "accept-language": "en-US"},
    )
    for c in registry.list_canaries():
        registry.record_exposure(
            canary_id=c.canary_id,
            session=session,
            ctx=ctx,
            resource="/docs",
            block_text=registry.injected_block_text(c),
            ts="2026-01-01T10:05:00.000000Z",
        )

    # 4. Ingest target and control datasets (t2: after exposure)
    dataset.ingest(
        sample_path,
        role="target",
        now="2026-01-01T10:10:00.000000Z",
    )
    control_file = _create_control_file(sample_path, tmp_path / "control.jsonl")
    control_ds = dataset.ingest(
        control_file,
        role="control",
        now="2026-01-01T10:10:01.000000Z",
    )

    # 5. Run investigate
    res = investigate.investigate(generate=stub_generate)
    case_id = res["case_id"]
    assert case_id == "SB-001"
    assert "target" in res["probe_ids"] and "control" in res["probe_ids"]

    # 6. Verify case details
    case = investigate.get_case("SB-001")
    assert case is not None
    assert case.status == "PROVENANCE_SIGNAL_DETECTED"

    findings_by_canary = {f.canary_id: f for f in case.findings}

    # Every canary's prompt retrieves its own chunk, so all five are detected and become OBSERVED.
    all_ids = [c.canary_id for c in registry.list_canaries()]
    assert sorted(findings_by_canary) == all_ids
    for cid in all_ids:
        assert findings_by_canary[cid].status == "PROVENANCE_SIGNAL_DETECTED"
        assert findings_by_canary[cid].exact_match is True
        c = registry.get(cid)
        assert c is not None
        assert c.status == "OBSERVED"

    # Evidence dir has 10 files
    bundle_dir = evidence_root / case.run_id / "SB-001"
    assert bundle_dir.is_dir()
    bundle_files = [f for f in bundle_dir.iterdir() if f.is_file()]
    assert len(bundle_files) == 10

    # Evidence verification is VALID
    v_res = evidence.verify_case("SB-001")
    assert v_res["result"] == "VALID"


    # Second investigate in the same run -> "SB-002". All canaries are now OBSERVED, so the default
    # EXPOSED-first selection finds none; name the canaries explicitly.
    res2 = investigate.investigate(canary_ids=all_ids, generate=stub_generate)
    assert res2["case_id"] == "SB-002"
    case2 = investigate.get_case("SB-002")
    assert case2 is not None
    assert case2.run_id == case.run_id

    # Negative: control dataset used as target -> case_id None and no cases row
    count_before = len(investigate.list_cases())
    res_neg = investigate.investigate(
        target_dataset_id=control_ds.dataset_id,
        control_dataset_id=control_ds.dataset_id,
        canary_ids=all_ids,
        generate=stub_generate,
    )
    assert res_neg["case_id"] is None
    count_after = len(investigate.list_cases())
    assert count_after == count_before


def test_investigate_no_datasets():
    # Empty database with no datasets -> ValueError
    db.reset_db()
    with pytest.raises(ValueError, match="no target dataset ingested"):
        investigate.investigate()
