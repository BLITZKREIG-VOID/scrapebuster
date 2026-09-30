#!/usr/bin/env python3
"""Verify preserved real Phase 11 inputs/evidence without rerunning attacks or the LLM."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sb.canary.hashing import normalize_for_match
from sb.provenance import correlate, evidence


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(handoff: Path, tamper_copy: bool = False) -> dict:
    summary = load(handoff)
    recovery = load(ROOT / summary["phase10_manifest"])
    require(summary["run_id"] == recovery["run_id"], "run identity mismatch")
    for role in ("target", "control"):
        source = recovery[role]
        path = ROOT / source["path"]
        require(sha(path) == source["sha256"] == summary[f"{role}_dataset"]["sha256"], f"{role} hash mismatch")
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        require(len(records) == source["records"] > 0, f"{role} count mismatch")
        require(all(set(r) == {"url", "fetched_at", "title", "text"} for r in records), f"{role} schema mismatch")
    for name, snapshot in recovery["snapshots"].items():
        path = ROOT / snapshot["path"]
        require(sha(path) == snapshot["sha256"], f"{name} snapshot hash mismatch")
        require(len(load(path)) == snapshot["rows"], f"{name} snapshot count mismatch")

    manifest_path = ROOT / summary["evidence_manifest"]
    chain = ROOT / summary["evidence_chain"]
    bundle = manifest_path.parent
    verification = evidence.verify_bundle(bundle, chain)
    require(verification["result"] == "VALID", f"evidence: {verification}")
    manifest = load(manifest_path)
    require(manifest["manifest_sha256"] == summary["manifest_sha256"], "manifest identity mismatch")
    require(sha(manifest_path) == summary["manifest_file_sha256"], "manifest file hash mismatch")
    finding = load(bundle / "09_finding.json")
    require(finding["run_id"] == summary["run_id"] and finding["case_id"] == summary["case_id"], "case identity mismatch")
    session = recovery["sessions"]["sophisticated_scraper"]["session_id"]
    require(finding["session_ids"] == summary["session_ids"] == [session], "case/session mismatch")
    events = load(ROOT / recovery["snapshots"]["traffic_events"]["path"])
    trap_hits = load(ROOT / recovery["snapshots"]["trap_hits"]["path"])
    exposures = load(bundle / "03_exposure_events.json")
    require(any(e["session_id"] == session and e["layer"] == "L2" and e["decision"] == "PASS" for e in events), "missing L2 PASS")
    require(any(e["session_id"] == session and e["layer"] == "L3" and e["decision"] == "TRAP" for e in events), "missing L3 TRAP")
    require(any(h["session_id"] == session and h["trap_id"] == "TRAP-ROBOTS-01" for h in trap_hits), "missing robots trap")
    require(len(exposures) == 5 and all(e["session_id"] == session for e in exposures), "exposure/session mismatch")
    human = recovery["sessions"]["human_control"]["session_id"]
    require(not any(e["session_id"] == human for e in exposures + trap_hits), "human was trapped/exposed")

    probes = {role: load(ROOT / path) for role, path in summary["probe_snapshots"].items()}
    canaries = load(bundle / "01_canary.json")
    publications = {p["canary_id"]: p for p in load(bundle / "02_publication_record.json")}
    probe_request = load(bundle / "05_probe_request.json")
    target_responses = load(bundle / "06_model_response.json")
    control_responses = load(bundle / "07_control_response.json")
    for role, responses in (("target", target_responses), ("control", control_responses)):
        probe = probes[role]
        require(probe["probe_id"] == summary["probe_ids"][role] and probe["status"] == "DONE", f"{role} probe identity mismatch")
        require(probe["dataset_sha256"] == recovery[role]["sha256"], f"{role} probe dataset mismatch")
        require(probe_request["datasets"][role]["dataset_id"] == probe["dataset_id"], f"{role} request dataset mismatch")
        require(probe["model"]["mode"] == "live" and probe["model"]["digest"] == summary["model"]["digest"], f"{role} model mismatch")
        by_canary = {r["canary_id"]: r for r in responses}
        for result in probe["results"]:
            require(hashlib.sha256(result["response_text"].encode()).hexdigest() == result["response_sha256"], "response hash mismatch")
            require(by_canary[result["canary_id"]]["response_sha256"] == result["response_sha256"], "bundle/probe output mismatch")

    target = {r["canary_id"]: r for r in probes["target"]["results"]}
    control = {r["canary_id"]: r for r in probes["control"]["results"]}
    control_records = [json.loads(line) for line in (ROOT / recovery["control"]["path"]).read_text().splitlines() if line.strip()]
    control_texts = [r["title"] + "\n" + r["text"] for r in control_records]
    baseline_texts = [json.loads(line)["text"] for line in (ROOT / "data/baseline/public_baseline.jsonl").read_text().splitlines() if line.strip()]
    findings, negative_findings = [], []
    for c in canaries:
        cid = c["canary_id"]
        require(not any(normalize_for_match(c["anchor"]) in normalize_for_match(t) for t in control_texts), "control contamination")
        common = dict(canary=c, publication=publications[cid], exposures=[e for e in exposures if e["canary_id"] == cid], control_response=control[cid]["response_text"], ingested_at=summary["target_dataset"]["ingested_at"], observed_at=target[cid]["ts"], control_texts=control_texts, baseline_texts=baseline_texts)
        findings.append(correlate.compute_finding(target_response=target[cid]["response_text"], **common))
        negative_findings.append(correlate.compute_finding(target_response=control[cid]["response_text"], **common))
    require(correlate.case_status(findings)[0] == "PROVENANCE_SIGNAL_DETECTED", "target lost signal")
    require(correlate.case_status(negative_findings)[0] == "NO_SIGNAL", "control not negative")
    require([f["status"] for f in findings] == [f["status"] for f in finding["findings"]], "stored correlation mismatch")

    tamper = "not_run"
    if tamper_copy:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "bundle"
            shutil.copytree(bundle, copied)
            victim = copied / "06_model_response.json"
            victim.chmod(0o644)
            victim.write_bytes(victim.read_bytes() + b"\nmodified\n")
            tamper = evidence.verify_bundle(copied, chain)["result"]
            require(tamper == "TAMPERED", "tamper not detected")
        require(evidence.verify_bundle(bundle, chain)["result"] == "VALID", "original evidence changed")
    return {"run_id": summary["run_id"], "case_id": summary["case_id"], "target": "PROVENANCE_SIGNAL_DETECTED", "control": "NO_SIGNAL", "verify": "VALID", "tamper_copy": tamper}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, default=ROOT / "data/phase11_handoff.json")
    parser.add_argument("--tamper-copy", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.handoff, args.tamper_copy), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
