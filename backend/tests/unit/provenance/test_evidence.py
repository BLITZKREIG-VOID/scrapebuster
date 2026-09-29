"""Unit tests for evidence bundle creation and tamper verification (PRV-05)."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from sb.canary import hashing, registry
from sb.provenance import evidence
from sb.store import db


def _create_test_canary_record() -> dict[str, Any]:
    """Build a canary record matching the seed pattern from registry definitions."""
    definitions = registry.load_definitions()
    assert len(definitions) > 0, "No canary definitions found in canaries.yaml"
    item = definitions[0]
    canonical = hashing.normalize(item["content"])
    canary_sha = hashing.canary_hash({
        "canary_id": item["canary_id"],
        "type": item["type"],
        "content": item["content"],
        "content_version": item["content_version"],
    })
    return {
        "canary_id": item["canary_id"],
        "type": item["type"],
        "canonical_content": canonical,
        "anchor": item.get("anchor", ""),
        "context_terms": item.get("context_terms", []),
        "probe_prompts": item.get("probe_prompts", []),
        "sha256": canary_sha,
        "content_version": item["content_version"],
        "created_at": registry.now_iso(),
        "published_at": registry.now_iso(),
        "status": "ACTIVE",
        "placements": item.get("placements", []),
    }


def _create_test_finding(case_id: str, canary_id: str) -> dict[str, Any]:
    """Build a finding record as a plain dict matching Finding fields."""
    return {
        "finding_id": f"{case_id}-F1",
        "canary_id": canary_id,
        "exact_match": True,
        "context_match": {"matched": True, "terms": ["nimbus", "warden"]},
        "uniqueness": "UNIQUE",
        "temporal": {"order_ok": True},
        "integrity": "VALID",
        "control_negative": True,
        "status": "PROVENANCE_SIGNAL_DETECTED",
        "confidence": "HIGH",
    }


def _create_test_case_payload(case_id: str, run_id: str) -> dict[str, Any]:
    """Build a complete case dict with bundle payloads for files 01..08."""
    canary_rec = _create_test_canary_record()
    finding_rec = _create_test_finding(case_id, canary_rec["canary_id"])
    created_at = registry.now_iso()

    target_resp = "Canary response text for testing."
    control_resp = "Control response text for testing."

    return {
        "case_id": case_id,
        "run_id": run_id,
        "created_at": created_at,
        "status": "PROVENANCE_SIGNAL_DETECTED",
        "confidence": "HIGH",
        "primary_canary_id": canary_rec["canary_id"],
        "session_ids": ["SES-0001"],
        "probe_ids": ["PRB-0001"],
        "findings": [finding_rec],
        "statement": "Synthetic canary detected in target model output.",
        "bundle": {
            "canaries": [canary_rec],
            "publications": [{
                "canary_id": canary_rec["canary_id"],
                "sha256": canary_rec["sha256"],
                "content_version": canary_rec["content_version"],
                "published_at": canary_rec["published_at"],
                "placements": canary_rec["placements"],
            }],
            "exposures": [{
                "exposure_id": "EXP-0001",
                "canary_id": canary_rec["canary_id"],
                "ts": created_at,
                "session_id": "SES-0001",
                "resource": "/docs/api",
                "content_version": canary_rec["content_version"],
                "content_sha256": hashing.block_hash(canary_rec["canonical_content"]),
                "client": {"ip": "10.0.0.1", "client_key": "CK-1", "classification": "SOPHISTICATED_SCRAPER"},
                "request": {"method": "GET", "path": "/docs/api"},
            }],
            "sessions": [{
                "session_id": "SES-0001",
                "client_key": "CK-1",
                "classification": "SOPHISTICATED_SCRAPER",
                "state": "TRAPPED",
            }],
            "probe_request": {
                "probe_id": "PRB-0001",
                "target": "target-model",
                "prompts": ["What is the endpoint?"],
                "model": {"name": "qwen2.5:3b", "digest": "sha256:test", "mode": "live"},
            },
            "target_responses": [{
                "prompt": "What is the endpoint?",
                "response_text": target_resp,
                "response_sha256": hashlib.sha256(target_resp.encode()).hexdigest(),
            }],
            "control_responses": [{
                "prompt": "What is the endpoint?",
                "response_text": control_resp,
                "response_sha256": hashlib.sha256(control_resp.encode()).hexdigest(),
            }],
            "match_analysis": {
                "exact_match": True,
                "context_match": True,
                "anchor": canary_rec["anchor"],
            },
        },
    }


def _insert_case_row(case_payload: dict[str, Any]) -> None:
    """Insert a placeholder cases row so the evidence UPDATE is observable."""
    with closing(db.get_connection()) as conn, conn:
        conn.execute(
            """
            INSERT INTO cases (
                case_id, run_id, created_at, status, confidence,
                primary_canary_id, session_ids, probe_ids, findings, evidence, statement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_payload["case_id"],
                case_payload["run_id"],
                case_payload["created_at"],
                case_payload["status"],
                case_payload["confidence"],
                case_payload["primary_canary_id"],
                json.dumps(case_payload["session_ids"]),
                json.dumps(case_payload["probe_ids"]),
                json.dumps(case_payload["findings"]),
                json.dumps({"status": "PENDING"}),
                case_payload["statement"],
            ),
        )


def test_t_ev_1_build_and_verify_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T-EV-1: build_bundle creates 10 files with correct hashes, genesis prev, chain linkage, and valid verification."""
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", evidence_root)

    run_id = "RUN-20260929-001"
    case_1_id = "SB-001"
    case_1 = _create_test_case_payload(case_1_id, run_id)
    _insert_case_row(case_1)

    # 1. Build bundle for case 1
    summary_1 = evidence.build_bundle(case_1)
    bundle_1_dir = evidence_root / run_id / case_1_id

    # Exactly 10 files
    files_on_disk = list(bundle_1_dir.iterdir())
    assert len(files_on_disk) == 10
    disk_file_names = {f.name for f in files_on_disk}
    assert disk_file_names == set(evidence.FILE_NAMES)

    # Manifest file hashes match disk
    manifest_path = bundle_1_dir / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest_data["files"]) == 9

    for file_info in manifest_data["files"]:
        target_file = bundle_1_dir / file_info["name"]
        content_bytes = target_file.read_bytes()
        assert hashlib.sha256(content_bytes).hexdigest() == file_info["sha256"]
        assert len(content_bytes) == file_info["bytes"]

    # Manifest self hash recomputes
    manifest_copy = dict(manifest_data)
    manifest_copy["manifest_sha256"] = ""
    recomputed_manifest_sha = hashlib.sha256(
        json.dumps(manifest_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert recomputed_manifest_sha == manifest_data["manifest_sha256"]

    # First prev == GENESIS
    assert manifest_data["prev_manifest_sha256"] == evidence.GENESIS
    assert summary_1["prev_manifest_sha256"] == evidence.GENESIS
    assert summary_1["manifest_sha256"] == manifest_data["manifest_sha256"]
    assert summary_1["status"] == "PRESERVED_LOCAL"
    assert summary_1["files"] == 10
    assert summary_1["local_path"] == str(bundle_1_dir)

    # File modes 0o444
    for f in files_on_disk:
        file_mode = stat.S_IMODE(f.stat().st_mode)
        assert file_mode == 0o444

    # 10 evidence_objects rows in DB
    with closing(db.get_connection()) as conn, conn:
        eo_rows = conn.execute(
            "SELECT name, sha256, bytes, local_path FROM evidence_objects WHERE case_id = ? ORDER BY name ASC",
            (case_1_id,),
        ).fetchall()
    assert len(eo_rows) == 10

    # Manifest row in evidence_objects has sha256 of manifest.json bytes
    manifest_eo_row = next(r for r in eo_rows if r["name"] == "manifest.json")
    manifest_disk_bytes = manifest_path.read_bytes()
    assert manifest_eo_row["sha256"] == hashlib.sha256(manifest_disk_bytes).hexdigest()
    assert manifest_eo_row["bytes"] == len(manifest_disk_bytes)

    # cases.evidence status PRESERVED_LOCAL
    with closing(db.get_connection()) as conn, conn:
        case_row = conn.execute("SELECT evidence FROM cases WHERE case_id = ?", (case_1_id,)).fetchone()
    stored_evidence = json.loads(case_row["evidence"])
    assert stored_evidence["status"] == "PRESERVED_LOCAL"
    assert stored_evidence["manifest_sha256"] == manifest_data["manifest_sha256"]
    assert stored_evidence["prev_manifest_sha256"] == evidence.GENESIS
    assert stored_evidence["files"] == 10

    # 2. Build second case: prev == first manifest_sha256, chain head == second
    case_2_id = "SB-002"
    case_2 = _create_test_case_payload(case_2_id, run_id)
    _insert_case_row(case_2)

    summary_2 = evidence.build_bundle(case_2)
    assert summary_2["prev_manifest_sha256"] == summary_1["manifest_sha256"]

    chain_path = evidence_root / "chain.json"
    assert chain_path.exists()
    chain_obj = json.loads(chain_path.read_text(encoding="utf-8"))
    assert chain_obj["head"] == summary_2["manifest_sha256"]
    assert len(chain_obj["entries"]) == 2
    assert chain_obj["entries"][0]["case_id"] == case_1_id
    assert chain_obj["entries"][0]["prev_manifest_sha256"] == evidence.GENESIS
    assert chain_obj["entries"][1]["case_id"] == case_2_id
    assert chain_obj["entries"][1]["prev_manifest_sha256"] == summary_1["manifest_sha256"]

    # 3. verify_case → VALID with every check ok
    verify_1 = evidence.verify_case(case_1_id)
    assert verify_1["result"] == "VALID"
    assert len(verify_1["checks"]) > 0
    assert all(c["ok"] for c in verify_1["checks"]), f"Failed checks: {[c for c in verify_1['checks'] if not c['ok']]}"

    verify_2 = evidence.verify_case(case_2_id)
    assert verify_2["result"] == "VALID"
    assert len(verify_2["checks"]) > 0
    assert all(c["ok"] for c in verify_2["checks"]), f"Failed checks: {[c for c in verify_2['checks'] if not c['ok']]}"


def test_t_ev_2_tamper_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T-EV-2: verify_bundle detects byte flips as TAMPERED while original remains VALID."""
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", evidence_root)

    run_id = "RUN-20260929-002"
    case_id = "SB-003"
    case_payload = _create_test_case_payload(case_id, run_id)
    _insert_case_row(case_payload)

    evidence.build_bundle(case_payload)
    original_bundle_dir = evidence_root / run_id / case_id

    # Copy bundle to tmp and chmod writable
    copy_dir = tmp_path / "tampered_bundle"
    shutil.copytree(original_bundle_dir, copy_dir)
    for p in copy_dir.iterdir():
        p.chmod(0o644)

    # Flip one byte in 06_model_response.json
    model_response_file = copy_dir / "06_model_response.json"
    content = bytearray(model_response_file.read_bytes())
    content[0] ^= 0x01
    model_response_file.write_bytes(bytes(content))

    # verify_bundle(copy) == TAMPERED with the file:06_model_response.json check failing
    tampered_result = evidence.verify_bundle(copy_dir)
    assert tampered_result["result"] == "TAMPERED"

    failed_checks = [c for c in tampered_result["checks"] if not c["ok"]]
    assert len(failed_checks) == 1
    assert failed_checks[0]["name"] == "file:06_model_response.json"

    # Original remains VALID
    orig_result = evidence.verify_bundle(original_bundle_dir)
    assert orig_result["result"] == "VALID"
    assert all(c["ok"] for c in orig_result["checks"])


def test_rebuild_same_case_raises_file_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rebuilding an existing case_id raises FileExistsError (never overwrite evidence)."""
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", evidence_root)

    run_id = "RUN-20260929-003"
    case_id = "SB-004"
    case_payload = _create_test_case_payload(case_id, run_id)
    _insert_case_row(case_payload)

    evidence.build_bundle(case_payload)

    with pytest.raises(FileExistsError):
        evidence.build_bundle(case_payload)


def test_mutated_canary_content_tamper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutating canonical_content in 01_canary.json causes canary_hashes and file check to fail."""
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", evidence_root)

    run_id = "RUN-20260929-004"
    case_id = "SB-005"
    case_payload = _create_test_case_payload(case_id, run_id)
    _insert_case_row(case_payload)

    evidence.build_bundle(case_payload)
    original_bundle_dir = evidence_root / run_id / case_id

    copy_dir = tmp_path / "canary_tamper_bundle"
    shutil.copytree(original_bundle_dir, copy_dir)
    for p in copy_dir.iterdir():
        p.chmod(0o644)

    canary_file = copy_dir / "01_canary.json"
    canaries = json.loads(canary_file.read_text(encoding="utf-8"))
    canaries[0]["canonical_content"] = canaries[0]["canonical_content"] + " [MUTATED]"
    canary_file.write_text(json.dumps(canaries, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    result = evidence.verify_bundle(copy_dir)
    assert result["result"] == "TAMPERED"

    failed_check_names = {c["name"] for c in result["checks"] if not c["ok"]}
    assert "file:01_canary.json" in failed_check_names
    assert "canary_hashes" in failed_check_names


def test_verify_case_unknown_id_raises_key_error() -> None:
    """verify_case with an unknown case_id raises KeyError."""
    with pytest.raises(KeyError):
        evidence.verify_case("NONEXISTENT-CASE-ID")


def test_tampered_manifest_self_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutating metadata in manifest.json without recomputing hash fails manifest_self_hash check."""
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", evidence_root)

    run_id = "RUN-20260929-005"
    case_id = "SB-006"
    case_payload = _create_test_case_payload(case_id, run_id)
    _insert_case_row(case_payload)

    evidence.build_bundle(case_payload)
    original_bundle_dir = evidence_root / run_id / case_id

    copy_dir = tmp_path / "manifest_tamper_bundle"
    shutil.copytree(original_bundle_dir, copy_dir)
    for p in copy_dir.iterdir():
        p.chmod(0o644)

    manifest_file = copy_dir / "manifest.json"
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest_data["tool_version"] = "scapebusters-tampered-9.9"
    manifest_file.write_text(json.dumps(manifest_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    result = evidence.verify_bundle(copy_dir)
    assert result["result"] == "TAMPERED"
    failed_names = {c["name"] for c in result["checks"] if not c["ok"]}
    assert "manifest_self_hash" in failed_names


def test_broken_chain_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tampering with chain.json causes chain_link check to fail."""
    evidence_root = tmp_path / "evidence"
    monkeypatch.setattr(evidence, "EVIDENCE_ROOT", evidence_root)

    run_id = "RUN-20260929-006"
    case_id = "SB-007"
    case_payload = _create_test_case_payload(case_id, run_id)
    _insert_case_row(case_payload)

    evidence.build_bundle(case_payload)
    bundle_dir = evidence_root / run_id / case_id

    # Tamper with chain.json
    chain_file = evidence_root / "chain.json"
    chain_obj = json.loads(chain_file.read_text(encoding="utf-8"))
    chain_obj["entries"][0]["manifest_sha256"] = "f" * 64
    chain_file.write_text(json.dumps(chain_obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    result = evidence.verify_bundle(bundle_dir, chain_path=chain_file)
    assert result["result"] == "TAMPERED"
    failed_names = {c["name"] for c in result["checks"] if not c["ok"]}
    assert "chain_link" in failed_names


def test_missing_manifest_returns_tampered_no_raise(tmp_path: Path) -> None:
    """verify_bundle returns TAMPERED when manifest.json is missing without raising exceptions."""
    empty_dir = tmp_path / "empty_bundle"
    empty_dir.mkdir()

    result = evidence.verify_bundle(empty_dir)
    assert result["result"] == "TAMPERED"
    assert all(not c["ok"] for c in result["checks"])
