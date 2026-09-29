"""Unit tests for provenance API routers (PRV-06)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from sb.api.canaries import CanaryDetail, router as canaries_router
from sb.api.cases import router as cases_router
from sb.api.datasets import router as datasets_router
from sb.api.probes import ProbeRun, router as probes_router
from sb.canary import registry
from sb.canary.seed import seed_canaries
from sb.contracts import Canary, Case, CaseSummary, Dataset
from sb.provenance import evidence, investigate, llm
from sb.provenance.llm import LLMResult
from sb.provenance.vault_s3 import s3_status


def _create_control_file(sample_path: Path, dest_path: Path) -> Path:
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


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(canaries_router, prefix="/api/v1")
    app.include_router(datasets_router, prefix="/api/v1")
    app.include_router(probes_router, prefix="/api/v1")
    app.include_router(cases_router, prefix="/api/v1")
    return app


def test_api_full_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_path: Path):
    app = create_test_app()
    client = TestClient(app)

    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr(
        llm,
        "model_info",
        lambda: {"name": "qwen2.5:3b", "digest": "sha256:apidigest"},
    )

    def stub_generate(prompt: str, fallback_text: str = "", replay_text: str | None = None) -> LLMResult:
        return LLMResult(
            text=fallback_text,
            mode="live",
            model_name="qwen2.5:3b",
            model_digest="sha256:apidigest",
            latency_ms=10,
        )

    monkeypatch.setattr(investigate, "GENERATE_FN", stub_generate)

    # 1. Test /probes/run 409 when no datasets exist
    res = client.post("/api/v1/probes/run", json={})
    assert res.status_code == 409
    assert "no target dataset" in res.json()["detail"].lower()

    # 2. Test /canaries endpoints before seed (empty)
    res = client.get("/api/v1/canaries")
    assert res.status_code == 200
    assert res.json()["canaries"] == []

    # 3. Seed canaries
    seed_canaries(now="2026-01-01T10:00:00.000000Z")

    # 4. GET /canaries lists 5 validating as Canary
    res = client.get("/api/v1/canaries")
    assert res.status_code == 200
    canary_list = res.json()["canaries"]
    assert len(canary_list) == 5
    for c_data in canary_list:
        c_obj = Canary.model_validate(c_data)
        assert c_obj.canary_id.startswith("SB-CAN-")

    # 5. GET /canaries/{id} success + 404
    res = client.get("/api/v1/canaries/SB-CAN-0001")
    assert res.status_code == 200
    detail = CanaryDetail.model_validate(res.json())
    assert detail.canary_id == "SB-CAN-0001"
    assert detail.publication is not None

    res = client.get("/api/v1/canaries/SB-CAN-UNKNOWN")
    assert res.status_code == 404

    # 6. Record exposures
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

    # 7. POST /datasets/ingest error paths: 404 (file not found), 400 (bad role), 400 (malformed JSON)
    res = client.post("/api/v1/datasets/ingest", json={"path": str(tmp_path / "missing.jsonl"), "role": "target"})
    assert res.status_code == 404

    res = client.post("/api/v1/datasets/ingest", json={"path": str(sample_path), "role": "invalid_role"})
    assert res.status_code == 400

    bad_json_file = tmp_path / "bad.jsonl"
    bad_json_file.write_text("not json\n", encoding="utf-8")
    res = client.post("/api/v1/datasets/ingest", json={"path": str(bad_json_file), "role": "target"})
    assert res.status_code == 400

    # 8. POST /datasets/ingest success for target and control
    res = client.post("/api/v1/datasets/ingest", json={"path": str(sample_path), "role": "target"})
    assert res.status_code == 200
    target_ds = Dataset.model_validate(res.json())
    assert target_ds.role == "target"

    control_file = _create_control_file(sample_path, tmp_path / "control.jsonl")
    res = client.post("/api/v1/datasets/ingest", json={"path": str(control_file), "role": "control"})
    assert res.status_code == 200
    control_ds = Dataset.model_validate(res.json())
    assert control_ds.role == "control"

    # 9. GET /datasets
    res = client.get("/api/v1/datasets")
    assert res.status_code == 200
    datasets = res.json()["datasets"]
    assert len(datasets) == 2

    # 10. POST /probes/run 400 on invalid dataset / invalid canary
    res = client.post("/api/v1/probes/run", json={"target_dataset_id": "DS-UNKNOWN"})
    assert res.status_code == 400

    res = client.post("/api/v1/probes/run", json={"canary_ids": ["SB-CAN-UNKNOWN"]})
    assert res.status_code == 400

    # 11. POST /probes/run success
    res = client.post("/api/v1/probes/run", json={})
    assert res.status_code == 200
    data = res.json()
    assert "probe_ids" in data
    assert data["case_id"] == "SB-001"
    target_probe_id = data["probe_ids"]["target"]

    # 12. GET /probes and GET /probes/{id}
    res = client.get("/api/v1/probes")
    assert res.status_code == 200
    probes = res.json()["probes"]
    assert len(probes) >= 2

    res = client.get(f"/api/v1/probes/{target_probe_id}")
    assert res.status_code == 200
    pr = ProbeRun.model_validate(res.json())
    assert pr.probe_id == target_probe_id
    assert len(pr.results) > 0

    res = client.get("/api/v1/probes/PRB-UNKNOWN")
    assert res.status_code == 404

    # 13. GET /cases
    res = client.get("/api/v1/cases")
    assert res.status_code == 200
    cases_list = res.json()
    assert len(cases_list) >= 1
    CaseSummary.model_validate(cases_list[0])

    # 14. GET /cases/{id} success + 404
    res = client.get("/api/v1/cases/SB-001")
    assert res.status_code == 200
    case_obj = Case.model_validate(res.json())
    assert case_obj.case_id == "SB-001"
    assert case_obj.status == "PROVENANCE_SIGNAL_DETECTED"

    res = client.get("/api/v1/cases/SB-999")
    assert res.status_code == 404

    # 15. GET /cases/{id}/evidence success + 404
    res = client.get("/api/v1/cases/SB-001/evidence")
    assert res.status_code == 200
    ev_data = res.json()
    assert "manifest" in ev_data
    assert "objects" in ev_data
    assert len(ev_data["objects"]) == 10
    assert ev_data["receipt"] is None

    res = client.get("/api/v1/cases/SB-999/evidence")
    assert res.status_code == 404

    # 16. POST /cases/{id}/verify success + 404
    res = client.post("/api/v1/cases/SB-001/verify")
    assert res.status_code == 200
    v_data = res.json()
    assert v_data["result"] == "VALID"

    res = client.post("/api/v1/cases/SB-999/verify")
    assert res.status_code == 404


def test_vault_s3_status(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SB_S3_BUCKET", raising=False)
    assert s3_status() == "disabled"

    monkeypatch.setenv("SB_S3_BUCKET", "my-test-bucket")
    assert s3_status() == "down"
