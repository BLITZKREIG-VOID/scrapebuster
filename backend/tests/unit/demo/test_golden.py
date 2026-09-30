"""Recorded fallback must retain provenance inputs across a real dataset reset."""
import json

from sb.demo import golden, reset, set_state
from sb.demo.runner import fresh_status
from sb.provenance import dataset, rag
from sb.store import db


def test_golden_restores_target_and_control_retrieval_after_reset(tmp_path, monkeypatch):
    datasets_dir = tmp_path / "datasets"
    evidence_dir = tmp_path / "evidence"
    golden_dir = tmp_path / "golden"
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "live.db"))
    monkeypatch.setattr(golden, "DATASETS_DIR", datasets_dir)
    monkeypatch.setattr(golden, "EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(golden, "GOLDEN_DIR", golden_dir)
    monkeypatch.setattr(reset, "DATASETS_DIR", datasets_dir)
    monkeypatch.setattr(dataset, "INGEST_DIR", datasets_dir / "ingested")
    db.reset_db()
    datasets_dir.mkdir()
    run_id = "RUN-golden-regression"
    target_path = datasets_dir / f"{run_id}_scraper3.jsonl"
    control_path = datasets_dir / "control.jsonl"
    for path, text in (
        (target_path, "CampusCart internal policy: Oriel Vantrask controls inventory reconciliation."),
        (control_path, "CampusCart public marketplace lists student books, rentals and campus events."),
    ):
        path.write_text(json.dumps({
            "url": "http://127.0.0.1:8000/", "fetched_at": "2026-09-30T00:00:00Z",
            "title": "CampusCart", "text": text,
        }) + "\n")
    target = dataset.ingest(target_path, "target")
    control = dataset.ingest(control_path, "control")
    (evidence_dir / run_id).mkdir(parents=True)
    (evidence_dir / "chain.json").write_text(json.dumps({"head": "0" * 64, "entries": []}))
    status = fresh_status(run_id)
    status["phase"] = "COMPLETE"
    for step in status["steps"]:
        step["status"] = "PASS"
    set_state("demo_status", status)
    set_state("run_id", run_id)
    set_state("demo_context", {"dataset_path": str(target_path)})
    try:
        golden.capture()
        reset._clear_datasets()
        db.reset_db()
        dataset.reset()
        rag.reset()
        restored = golden.restore()
        assert restored["mode"] == "golden"
        target_chunks = rag.retrieve(target.dataset_id, "Oriel Vantrask inventory reconciliation")
        control_chunks = rag.retrieve(control.dataset_id, "student books rentals")
        assert any("Oriel Vantrask" in text for _, _, text in target_chunks)
        assert all("Oriel Vantrask" not in text for _, _, text in control_chunks)
        assert any("student books" in text for _, _, text in control_chunks)
    finally:
        dataset.reset()
        rag.reset()
