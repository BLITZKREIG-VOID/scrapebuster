"""Unit tests for sb.provenance.correlate."""

from __future__ import annotations

from pathlib import Path

import yaml
from sb.canary import hashing
from sb.provenance.correlate import (
    build_statement,
    case_status,
    compute_finding,
    evaluate,
)

CANARIES_YAML_PATH = Path(__file__).parents[3] / "sb" / "canary" / "canaries.yaml"


def _load_canaries() -> list[dict]:
    with open(CANARIES_YAML_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)["canaries"]

    canaries = []
    for item in raw:
        canonical_content = hashing.normalize(item["content"])
        sha = hashing.canary_hash(
            {
                "canary_id": item["canary_id"],
                "type": item["type"],
                "content": canonical_content,
                "content_version": item["content_version"],
            }
        )
        c = {
            "canary_id": item["canary_id"],
            "type": item["type"],
            "content_version": item["content_version"],
            "canonical_content": canonical_content,
            "anchor": item["anchor"],
            "context_terms": item["context_terms"],
            "probe_prompts": item["probe_prompts"],
            "placements": item["placements"],
            "sha256": sha,
        }
        canaries.append(c)
    return canaries


t0 = "2026-09-01T10:00:00Z"
t1 = "2026-09-02T10:00:00Z"
t2 = "2026-09-03T10:00:00Z"
t3 = "2026-09-04T10:00:00Z"


def test_t_co_1_all_detected_high() -> None:
    canaries = _load_canaries()
    inputs = []

    for c in canaries:
        pub = {"published_at": t0}
        exp = {
            "exposure_id": "EXP-001",
            "canary_id": c["canary_id"],
            "ts": t1,
            "session_id": "SES-100",
            "resource": "/docs/test",
            "content_version": c["content_version"],
            "content_sha256": hashing.block_hash(c["canonical_content"]),
            "client": {"classification": "SOPHISTICATED_SCRAPER"},
            "request": {},
        }
        inp = {
            "canary": c,
            "publication": pub,
            "exposures": [exp],
            "target_response": c["canonical_content"],
            "control_response": "Generic response with no canary data.",
            "ingested_at": t2,
            "observed_at": t3,
            "control_texts": ["Generic control document text."],
            "baseline_texts": ["Generic public baseline paragraph."],
        }
        inputs.append(inp)

    findings = evaluate("SB-001", inputs)
    assert len(findings) == 5

    expected_ids = [f"SB-001-F{k}" for k in range(1, 6)]
    actual_ids = [f.finding_id for f in findings]
    assert actual_ids == expected_ids

    for f in findings:
        assert f.status == "PROVENANCE_SIGNAL_DETECTED"
        assert f.confidence == "HIGH"
        assert f.exact_match is True
        assert f.context_match["ok"] is True
        assert f.uniqueness == "UNIQUE"
        assert f.temporal["ordered"] is True
        assert f.integrity == "VALID"
        assert f.control_negative is True

    status, conf = case_status(findings)
    assert status == "PROVENANCE_SIGNAL_DETECTED"
    assert conf == "HIGH"


def test_t_co_2_all_no_signal() -> None:
    canaries = _load_canaries()
    inputs = []

    for c in canaries:
        pub = {"published_at": t0}
        exp = {
            "exposure_id": "EXP-001",
            "canary_id": c["canary_id"],
            "ts": t1,
            "session_id": "SES-100",
            "resource": "/docs/test",
            "content_version": c["content_version"],
            "content_sha256": hashing.block_hash(c["canonical_content"]),
            "client": {"classification": "SOPHISTICATED_SCRAPER"},
            "request": {},
        }
        inp = {
            "canary": c,
            "publication": pub,
            "exposures": [exp],
            "target_response": "Generic target output with no canary terms.",
            "control_response": "Generic control output with no canary terms.",
            "ingested_at": t2,
            "observed_at": t3,
            "control_texts": ["Generic control text."],
            "baseline_texts": ["Generic baseline text."],
        }
        inputs.append(inp)

    findings = evaluate("SB-002", inputs)
    assert len(findings) == 5

    for f in findings:
        assert f.status == "NO_SIGNAL"
        assert f.confidence == "NONE"

    status, conf = case_status(findings)
    assert status == "NO_SIGNAL"
    assert conf == "NONE"


def test_t_co_3_inconclusive_and_invalid_variants() -> None:
    canaries = _load_canaries()
    c = canaries[0]
    pub = {"published_at": t0}
    exp = {
        "exposure_id": "EXP-001",
        "canary_id": c["canary_id"],
        "ts": t1,
        "session_id": "SES-100",
        "resource": "/docs/test",
        "content_version": c["content_version"],
        "content_sha256": hashing.block_hash(c["canonical_content"]),
        "client": {"classification": "SOPHISTICATED_SCRAPER"},
        "request": {},
    }

    # 1. observed_at before published_at -> INCONCLUSIVE
    f_unordered = compute_finding(
        canary=c,
        publication=pub,
        exposures=[exp],
        target_response=c["canonical_content"],
        control_response="Generic control.",
        ingested_at=t2,
        observed_at="2026-08-01T00:00:00Z",  # before t0
        control_texts=[],
        baseline_texts=[],
    )
    assert f_unordered["temporal"]["ordered"] is False
    assert f_unordered["status"] == "INCONCLUSIVE"

    # 2. Mutated canonical_content (sha256 unchanged) -> INVALID and INCONCLUSIVE
    c_mutated = dict(c)
    c_mutated["canonical_content"] = c["canonical_content"] + " (edited)"
    f_mutated = compute_finding(
        canary=c_mutated,
        publication=pub,
        exposures=[exp],
        target_response=c_mutated["canonical_content"],
        control_response="Generic control.",
        ingested_at=t2,
        observed_at=t3,
        control_texts=[],
        baseline_texts=[],
    )
    assert f_mutated["integrity"] == "INVALID"
    assert f_mutated["status"] == "INCONCLUSIVE"

    # 3. control_response containing the anchor -> INCONCLUSIVE
    f_ctrl_pos = compute_finding(
        canary=c,
        publication=pub,
        exposures=[exp],
        target_response=c["canonical_content"],
        control_response=f"Control response mentioning {c['anchor']}",
        ingested_at=t2,
        observed_at=t3,
        control_texts=[],
        baseline_texts=[],
    )
    assert f_ctrl_pos["control_negative"] is False
    assert f_ctrl_pos["status"] == "INCONCLUSIVE"

    # 4. Anchor present in baseline -> NOT_UNIQUE and INCONCLUSIVE
    f_not_unique = compute_finding(
        canary=c,
        publication=pub,
        exposures=[exp],
        target_response=c["canonical_content"],
        control_response="Generic control.",
        ingested_at=t2,
        observed_at=t3,
        control_texts=[],
        baseline_texts=[f"Baseline paragraph containing {c['anchor']}"],
    )
    assert f_not_unique["uniqueness"] == "NOT_UNIQUE"
    assert f_not_unique["status"] == "INCONCLUSIVE"

    # 5. exposure content_sha256 mismatch -> INVALID
    exp_bad_hash = dict(exp)
    exp_bad_hash["content_sha256"] = "invalid_hash_value"
    f_bad_exp = compute_finding(
        canary=c,
        publication=pub,
        exposures=[exp_bad_hash],
        target_response=c["canonical_content"],
        control_response="Generic control.",
        ingested_at=t2,
        observed_at=t3,
        control_texts=[],
        baseline_texts=[],
    )
    assert f_bad_exp["integrity"] == "INVALID"


def test_exact_without_context_detected_medium() -> None:
    canaries = _load_canaries()
    c = canaries[0]
    pub = {"published_at": t0}
    exp = {
        "exposure_id": "EXP-001",
        "canary_id": c["canary_id"],
        "ts": t1,
        "session_id": "SES-100",
        "resource": "/docs/test",
        "content_version": c["content_version"],
        "content_sha256": hashing.block_hash(c["canonical_content"]),
        "client": {"classification": "SOPHISTICATED_SCRAPER"},
        "request": {},
    }

    # target_response contains ONLY the anchor (no context terms)
    f = compute_finding(
        canary=c,
        publication=pub,
        exposures=[exp],
        target_response=c["anchor"],
        control_response="Generic control.",
        ingested_at=t2,
        observed_at=t3,
        control_texts=[],
        baseline_texts=[],
    )
    assert f["exact_match"] is True
    assert f["context_match"]["ok"] is False
    assert f["status"] == "PROVENANCE_SIGNAL_DETECTED"
    assert f["confidence"] == "MEDIUM"


def test_partial_signal_low() -> None:
    canaries = _load_canaries()
    c = canaries[0]
    pub = {"published_at": t0}
    exp = {
        "exposure_id": "EXP-001",
        "canary_id": c["canary_id"],
        "ts": t1,
        "session_id": "SES-100",
        "resource": "/docs/test",
        "content_version": c["content_version"],
        "content_sha256": hashing.block_hash(c["canonical_content"]),
        "client": {"classification": "SOPHISTICATED_SCRAPER"},
        "request": {},
    }

    # target_response contains all 3 context terms but NOT the anchor
    target_text = " ".join(c["context_terms"]) + " without the doctor name"
    f = compute_finding(
        canary=c,
        publication=pub,
        exposures=[exp],
        target_response=target_text,
        control_response="Generic control.",
        ingested_at=t2,
        observed_at=t3,
        control_texts=[],
        baseline_texts=[],
    )
    assert f["exact_match"] is False
    assert len(f["context_match"]["matched"]) >= 3
    assert f["status"] == "PARTIAL_SIGNAL"
    assert f["confidence"] == "LOW"


def test_build_statement() -> None:
    case_filled = {
        "published_at": t0,
        "session_id": "SES-999",
        "classified_at": t1,
        "observed_at": t3,
    }
    stmt = build_statement(case_filled)
    expected = (
        f"The target model's output reproduced a unique synthetic canary that was published on {t0}, "
        f"served only to session SES-999 classified SOPHISTICATED_SCRAPER at {t1}, and observed in model "
        f"output at {t3}, while a control model built without that data did not reproduce it. "
        "This is a high-confidence provenance signal. It does not by itself establish intent, "
        "identity of the operator, or legal causation."
    )
    assert stmt == expected

    case_empty: dict = {}
    stmt_unknown = build_statement(case_empty)
    expected_unknown = (
        "The target model's output reproduced a unique synthetic canary that was published on unknown, "
        "served only to session unknown classified SOPHISTICATED_SCRAPER at unknown, and observed in model "
        "output at unknown, while a control model built without that data did not reproduce it. "
        "This is a high-confidence provenance signal. It does not by itself establish intent, "
        "identity of the operator, or legal causation."
    )
    assert stmt_unknown == expected_unknown
