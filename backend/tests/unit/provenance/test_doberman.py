"""Unit tests for Doberman probe runner (master plan §10)."""

from contextlib import closing
from datetime import datetime
import hashlib
from pathlib import Path
import re
import pytest

from sb.canary import registry
from sb.canary.seed import seed_canaries
from sb.provenance import dataset, llm, rag
from sb.provenance.doberman import get_probe, list_probes, run_probe, select_canaries
from sb.provenance.llm import LLMResult
from sb.store import db


def test_t_pr_1_stub_probe(sample_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
    """T-PR-1: stub generate returning LLMResult(text=f"stub:{prompt[-40:]}", mode="live", ...).

    Verify:
    - 2 ids matching ^PRB-[0-9a-f]{8}$
    - each run DONE with 5 results
    - total probe_results rows == 10
    - each response_sha256 == sha256(response_text)
    - target and control prompts per canary end with the same question
    - retrieved <= 3 items with chunk_id/score
    - model.mode == "live"
    """
    seed_canaries()
    target_ds = dataset.ingest(sample_path, role="target")
    baseline_path = repo_root / "data" / "baseline" / "public_baseline.jsonl"
    control_ds = dataset.ingest(baseline_path, role="control")

    monkeypatch.setattr(llm, "model_info", lambda: {"name": "stub", "digest": "d"})

    def stub_generate(prompt: str, fallback_text: str = "", replay_text: str | None = None) -> LLMResult:
        return LLMResult(
            text=f"stub:{prompt[-40:]}",
            mode="live",
            model_name="stub",
            model_digest="d",
            latency_ms=1,
        )

    probe_id_target, probe_id_control = run_probe(
        target_ds.dataset_id,
        control_ds.dataset_id,
        generate=stub_generate,
    )

    # 2 ids matching ^PRB-[0-9a-f]{8}$
    assert re.match(r"^PRB-[0-9a-f]{8}$", probe_id_target)
    assert re.match(r"^PRB-[0-9a-f]{8}$", probe_id_control)
    assert probe_id_target != probe_id_control

    target_probe = get_probe(probe_id_target)
    control_probe = get_probe(probe_id_control)
    assert target_probe is not None
    assert control_probe is not None

    # Each run DONE with 5 results
    assert target_probe["status"] == "DONE"
    assert control_probe["status"] == "DONE"
    assert len(target_probe["results"]) == 5
    assert len(control_probe["results"]) == 5

    # Total probe_results rows == 10
    with closing(db.get_connection()) as conn:
        count = conn.execute("SELECT COUNT(*) FROM probe_results").fetchone()[0]
        assert count == 10

    # Each response_sha256 == sha256(response_text)
    for probe in (target_probe, control_probe):
        for r in probe["results"]:
            expected_sha = hashlib.sha256(r["response_text"].encode("utf-8")).hexdigest()
            assert r["response_sha256"] == expected_sha

    # Target and control prompts per canary end with the same question
    canaries = {c.canary_id: c for c in registry.list_canaries()}
    t_by_canary = {r["canary_id"]: r for r in target_probe["results"]}
    c_by_canary = {r["canary_id"]: r for r in control_probe["results"]}

    for cid, canary in canaries.items():
        question = canary.probe_prompts[0]
        assert t_by_canary[cid]["prompt"].endswith(question)
        assert c_by_canary[cid]["prompt"].endswith(question)

    # Retrieved <= 3 items with chunk_id/score
    for probe in (target_probe, control_probe):
        for r in probe["results"]:
            assert len(r["retrieved"]) <= 3
            for item in r["retrieved"]:
                assert "chunk_id" in item
                assert "score" in item

    # model.mode == "live"
    assert target_probe["model"]["mode"] == "live"
    assert control_probe["model"]["mode"] == "live"
    assert target_probe["model"]["name"] == "stub"
    assert target_probe["model"]["digest"] == "d"
    assert control_probe["model"]["name"] == "stub"
    assert control_probe["model"]["digest"] == "d"


def test_t_pr_2_real_llm_fallback(sample_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
    """T-PR-2 (probe part): closed port triggers extractive_fallback with real llm.generate.

    Verify:
    - both runs DONE
    - every model.modes value "extractive_fallback"
    - target response for each canary equals that run's top retrieved chunk text
    - model.mode == "extractive_fallback"
    """
    seed_canaries()
    target_ds = dataset.ingest(sample_path, role="target")
    baseline_path = repo_root / "data" / "baseline" / "public_baseline.jsonl"
    control_ds = dataset.ingest(baseline_path, role="control")

    monkeypatch.setenv("SB_OLLAMA_URL", "http://127.0.0.1:9")

    # Run with the real llm.generate (no generate stub passed)
    probe_id_t, probe_id_c = run_probe(target_ds.dataset_id, control_ds.dataset_id)

    target_probe = get_probe(probe_id_t)
    control_probe = get_probe(probe_id_c)
    assert target_probe is not None
    assert control_probe is not None

    # Both runs DONE
    assert target_probe["status"] == "DONE"
    assert control_probe["status"] == "DONE"

    # model.mode == "extractive_fallback"
    assert target_probe["model"]["mode"] == "extractive_fallback"
    assert control_probe["model"]["mode"] == "extractive_fallback"

    # Every model.modes value "extractive_fallback"
    assert len(target_probe["model"]["modes"]) == 5
    assert len(control_probe["model"]["modes"]) == 5
    assert all(m == "extractive_fallback" for m in target_probe["model"]["modes"].values())
    assert all(m == "extractive_fallback" for m in control_probe["model"]["modes"].values())

    # Target response for each canary equals that run's top retrieved chunk text
    canaries = {c.canary_id: c for c in registry.list_canaries()}
    for r in target_probe["results"]:
        canary = canaries[r["canary_id"]]
        hits = rag.retrieve(target_ds.dataset_id, canary.probe_prompts[0], k=3)
        expected_top_text = hits[0][2] if hits else ""
        assert r["response_text"] == expected_top_text


def test_selection_and_dataset_validation(sample_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Canary selection rules, fallback behavior, and dataset error checking."""
    seed_canaries()

    # 1. No exposures -> 5 ACTIVE probed
    active_canaries = select_canaries()
    assert len(active_canaries) == 5
    assert all(c.status == "ACTIVE" for c in active_canaries)
    assert [c.canary_id for c in active_canaries] == [
        "SB-CAN-0001",
        "SB-CAN-0002",
        "SB-CAN-0003",
        "SB-CAN-0004",
        "SB-CAN-0005",
    ]

    # 2. After registry.set_status("SB-CAN-0002", "EXPOSED") only SB-CAN-0002
    registry.set_status("SB-CAN-0002", "EXPOSED")
    exposed_canaries = select_canaries()
    assert len(exposed_canaries) == 1
    assert exposed_canaries[0].canary_id == "SB-CAN-0002"
    assert exposed_canaries[0].status == "EXPOSED"

    # 3. SB_PROBE_CANARIES="SB-CAN-0001, SB-CAN-0003" limits to those two
    seed_canaries()  # Resets all to ACTIVE
    monkeypatch.setenv("SB_PROBE_CANARIES", "SB-CAN-0001, SB-CAN-0003")
    filtered = select_canaries()
    assert [c.canary_id for c in filtered] == ["SB-CAN-0001", "SB-CAN-0003"]
    monkeypatch.delenv("SB_PROBE_CANARIES", raising=False)

    # 4. Explicit canary_ids wins over status
    registry.set_status("SB-CAN-0002", "EXPOSED")
    explicit = select_canaries(["SB-CAN-0001", "SB-CAN-0004"])
    assert [c.canary_id for c in explicit] == ["SB-CAN-0001", "SB-CAN-0004"]

    # Unknown canary id raises KeyError
    with pytest.raises(KeyError, match="Unknown canary: SB-CAN-NONEXISTENT"):
        select_canaries(["SB-CAN-NONEXISTENT"])

    # 5. Unknown dataset -> KeyError and zero probe_runs rows
    target_ds = dataset.ingest(sample_path, role="target")
    baseline_path = repo_root / "data" / "baseline" / "public_baseline.jsonl"
    control_ds = dataset.ingest(baseline_path, role="control")

    with pytest.raises(KeyError, match="Target dataset not found: DS-bad"):
        run_probe("DS-bad", control_ds.dataset_id)
    assert len(list_probes()) == 0

    with pytest.raises(KeyError, match="Control dataset not found: DS-bad"):
        run_probe(target_ds.dataset_id, "DS-bad")
    assert len(list_probes()) == 0

    # 6. No canaries selected -> ValueError and zero probe_runs rows
    monkeypatch.setenv("SB_PROBE_CANARIES", "SB-CAN-NONE")
    with pytest.raises(ValueError, match="No canaries selected"):
        run_probe(target_ds.dataset_id, control_ds.dataset_id)
    assert len(list_probes()) == 0


def test_failure_handling(sample_path: Path, repo_root: Path):
    """Stub raising RuntimeError on 2nd call propagates and marks run FAILED with finished_at."""
    seed_canaries()
    target_ds = dataset.ingest(sample_path, role="target")
    baseline_path = repo_root / "data" / "baseline" / "public_baseline.jsonl"
    control_ds = dataset.ingest(baseline_path, role="control")

    call_count = 0

    def failing_generate(prompt: str, fallback_text: str = "", replay_text: str | None = None) -> LLMResult:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("LLM failure on 2nd call")
        return LLMResult(
            text="stub_response",
            mode="live",
            model_name="stub",
            model_digest="d",
            latency_ms=1,
        )

    with pytest.raises(RuntimeError, match="LLM failure on 2nd call"):
        run_probe(target_ds.dataset_id, control_ds.dataset_id, generate=failing_generate)

    probes = list_probes()
    assert len(probes) == 1
    failed_probe = probes[0]
    assert failed_probe["target"] == "target"
    assert failed_probe["status"] == "FAILED"
    assert failed_probe["finished_at"] is not None

    # Verify only target probe was inserted and control was not started
    with closing(db.get_connection()) as conn:
        runs = conn.execute("SELECT target, status FROM probe_runs").fetchall()
        assert len(runs) == 1
        assert runs[0]["target"] == "target"
        assert runs[0]["status"] == "FAILED"
        # First canary succeeded before 2nd failed, so exactly 1 result row was committed
        res_count = conn.execute("SELECT COUNT(*) FROM probe_results").fetchone()[0]
        assert res_count == 1


def test_get_probe_and_list_probes_shapes(sample_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify get_probe and list_probes dict structures and ordering."""
    assert get_probe("PRB-nonexistent") is None
    assert list_probes() == []

    seed_canaries()
    target_ds = dataset.ingest(sample_path, role="target")
    baseline_path = repo_root / "data" / "baseline" / "public_baseline.jsonl"
    control_ds = dataset.ingest(baseline_path, role="control")

    monkeypatch.setattr(llm, "model_info", lambda: {"name": "stub", "digest": "d"})

    call_index = 0

    def mixed_stub(prompt: str, fallback_text: str = "", replay_text: str | None = None) -> LLMResult:
        nonlocal call_index
        call_index += 1
        mode = "live" if call_index % 2 == 1 else "replay"
        return LLMResult(
            text="resp",
            mode=mode,
            model_name="stub",
            model_digest="d",
            latency_ms=10,
        )

    t_id, c_id = run_probe(
        target_ds.dataset_id,
        control_ds.dataset_id,
        canary_ids=["SB-CAN-0001", "SB-CAN-0002"],
        generate=mixed_stub,
    )

    probe = get_probe(t_id)
    assert probe is not None

    expected_keys = {
        "probe_id",
        "target",
        "status",
        "dataset_id",
        "dataset_sha256",
        "started_at",
        "finished_at",
        "model",
        "results",
    }
    assert set(probe.keys()) == expected_keys
    assert probe["probe_id"] == t_id
    assert probe["target"] == "target"
    assert probe["status"] == "DONE"
    assert probe["dataset_id"] == target_ds.dataset_id
    assert probe["dataset_sha256"] == target_ds.sha256
    assert isinstance(probe["model"], dict)
    assert probe["model"]["mode"] == "mixed"
    assert probe["model"]["modes"] == {"SB-CAN-0001": "live", "SB-CAN-0002": "replay"}
    assert isinstance(probe["results"], list)
    assert len(probe["results"]) == 2

    expected_res_keys = {
        "result_id",
        "canary_id",
        "prompt",
        "retrieved",
        "response_text",
        "response_sha256",
        "latency_ms",
        "ts",
    }
    for r in probe["results"]:
        assert set(r.keys()) == expected_res_keys
        assert isinstance(r["retrieved"], list)
        assert isinstance(r["latency_ms"], int)

    # Results are ordered by canary_id
    result_canaries = [r["canary_id"] for r in probe["results"]]
    assert result_canaries == ["SB-CAN-0001", "SB-CAN-0002"]

    # list_probes contains both runs, ordered by started_at desc
    all_probes = list_probes()
    assert len(all_probes) == 2
    for p in all_probes:
        assert set(p.keys()) == expected_keys
    assert {p["probe_id"] for p in all_probes} == {t_id, c_id}
    assert datetime.fromisoformat(all_probes[0]["started_at"]) >= datetime.fromisoformat(all_probes[1]["started_at"])
