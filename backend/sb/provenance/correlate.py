"""Correlation engine for provenance signals (master plan §11)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sb.canary import hashing
from sb.contracts import Finding

STATUS_RANK = {
    "PROVENANCE_SIGNAL_DETECTED": 3,
    "PARTIAL_SIGNAL": 2,
    "INCONCLUSIVE": 1,
    "NO_SIGNAL": 0,
}

STATEMENT_TEMPLATE = (
    "The target model's output reproduced a unique synthetic canary that was published on <t0>, "
    "served only to session <sid> classified SOPHISTICATED_SCRAPER at <t1>, and observed in model "
    "output at <t3>, while a control model built without that data did not reproduce it. "
    "This is a high-confidence provenance signal. It does not by itself establish intent, "
    "identity of the operator, or legal causation."
)


def compute_finding(
    canary: dict[str, Any],
    publication: dict[str, Any] | None,
    exposures: list[dict[str, Any]],
    target_response: str,
    control_response: str,
    ingested_at: str | None,
    observed_at: str | None,
    control_texts: list[str],
    baseline_texts: list[str],
) -> dict[str, Any]:
    norm_anchor = hashing.normalize_for_match(canary["anchor"])
    norm_target_resp = hashing.normalize_for_match(target_response)
    norm_control_resp = hashing.normalize_for_match(control_response)

    exact_match = norm_anchor in norm_target_resp

    context_terms = canary.get("context_terms", [])
    matched = [
        term
        for term in context_terms
        if hashing.normalize_for_match(term) in norm_target_resp
    ]
    context_match = {"matched": matched, "required": 2, "ok": len(matched) >= 2}

    in_control = any(
        norm_anchor in hashing.normalize_for_match(t) for t in control_texts
    )
    in_baseline = any(
        norm_anchor in hashing.normalize_for_match(t) for t in baseline_texts
    )
    uniqueness = "UNIQUE" if (not in_control and not in_baseline) else "NOT_UNIQUE"

    first_exposed_at = None
    if exposures:
        first_exposed_at = min(
            exposures,
            key=lambda e: datetime.fromisoformat(e["ts"].replace("Z", "+00:00")),
        )["ts"]

    pub_ts = publication["published_at"] if publication and publication.get("published_at") else None

    ordered = False
    if pub_ts is not None and first_exposed_at is not None and ingested_at is not None and observed_at is not None:
        try:
            dt_pub = datetime.fromisoformat(pub_ts.replace("Z", "+00:00"))
            dt_exp = datetime.fromisoformat(first_exposed_at.replace("Z", "+00:00"))
            dt_ing = datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
            dt_obs = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            ordered = dt_pub < dt_exp < dt_ing < dt_obs
        except Exception:
            ordered = False

    temporal = {
        "published_at": pub_ts,
        "first_exposed_at": first_exposed_at,
        "ingested_at": ingested_at,
        "observed_at": observed_at,
        "ordered": ordered,
    }

    canonical_content = canary.get("canonical_content", canary.get("content", ""))
    record = {
        "canary_id": canary["canary_id"],
        "type": canary["type"],
        "content": canonical_content,
        "content_version": canary["content_version"],
    }
    canary_hash_valid = hashing.canary_hash(record) == canary["sha256"]
    expected_block_hash = hashing.block_hash(canonical_content)
    exposures_valid = all(e.get("content_sha256") == expected_block_hash for e in exposures)
    integrity = "VALID" if (canary_hash_valid and exposures_valid) else "INVALID"

    control_negative = norm_anchor not in norm_control_resp

    has_signal = exact_match or context_match["ok"]
    is_valid = integrity == "VALID"
    is_unique = uniqueness == "UNIQUE"
    is_ordered = temporal["ordered"]

    if exact_match and is_unique and is_ordered and is_valid and control_negative:
        status = "PROVENANCE_SIGNAL_DETECTED"
    elif (not exact_match) and len(matched) >= 3 and is_unique and is_ordered and is_valid and control_negative:
        status = "PARTIAL_SIGNAL"
    elif (not control_negative) or (has_signal and (not is_valid or not is_unique or not is_ordered)):
        status = "INCONCLUSIVE"
    else:
        status = "NO_SIGNAL"

    if status == "PROVENANCE_SIGNAL_DETECTED":
        confidence = "HIGH" if context_match["ok"] else "MEDIUM"
    elif status == "PARTIAL_SIGNAL":
        confidence = "LOW"
    else:
        confidence = "NONE"

    return {
        "canary_id": canary["canary_id"],
        "exact_match": exact_match,
        "context_match": context_match,
        "uniqueness": uniqueness,
        "temporal": temporal,
        "integrity": integrity,
        "control_negative": control_negative,
        "status": status,
        "confidence": confidence,
    }


def evaluate(case_id: str, inputs: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    for k, inp in enumerate(inputs, start=1):
        f_dict = compute_finding(**inp)
        f_dict["finding_id"] = f"{case_id}-F{k}"
        findings.append(Finding(**f_dict))
    return findings


def case_status(findings: list[Finding | dict[str, Any]]) -> tuple[str, str]:
    if not findings:
        return "NO_SIGNAL", "NONE"

    status_list: list[str] = []
    conf_list: list[str] = []
    for f in findings:
        if isinstance(f, dict):
            status_list.append(f.get("status", "NO_SIGNAL"))
            conf_list.append(f.get("confidence", "NONE"))
        else:
            status_list.append(getattr(f, "status", "NO_SIGNAL"))
            conf_list.append(getattr(f, "confidence", "NONE"))

    status = max(status_list, key=lambda s: STATUS_RANK.get(s, 0))

    high_count = sum(1 for c in conf_list if c == "HIGH")
    if high_count >= 3:
        confidence = "HIGH"
    elif status == "PROVENANCE_SIGNAL_DETECTED":
        confidence = "MEDIUM"
    elif status == "PARTIAL_SIGNAL":
        confidence = "LOW"
    else:
        confidence = "NONE"

    return status, confidence


def build_statement(case: dict[str, Any] | Any) -> str:
    def _get_val(obj: Any, keys: list[str]) -> str | None:
        for key in keys:
            if isinstance(obj, dict):
                val = obj.get(key)
            else:
                val = getattr(obj, key, None)
            if val is not None and str(val).strip():
                return str(val)
        return None

    t0 = _get_val(case, ["published_at", "t0"])
    sid = _get_val(case, ["session_id", "sid"])
    if sid is None:
        session_ids = case.get("session_ids") if isinstance(case, dict) else getattr(case, "session_ids", None)
        if session_ids and len(session_ids) > 0:
            sid = str(session_ids[0])

    t1 = _get_val(case, ["classified_at", "first_exposed_at", "t1"])
    t3 = _get_val(case, ["observed_at", "t3"])

    findings = case.get("findings") if isinstance(case, dict) else getattr(case, "findings", None)
    if findings and len(findings) > 0:
        f0 = findings[0]
        temporal = f0.get("temporal") if isinstance(f0, dict) else getattr(f0, "temporal", None)
        if temporal:
            if t0 is None:
                t0 = temporal.get("published_at") if isinstance(temporal, dict) else getattr(temporal, "published_at", None)
            if t1 is None:
                t1 = temporal.get("first_exposed_at") if isinstance(temporal, dict) else getattr(temporal, "first_exposed_at", None)
            if t3 is None:
                t3 = temporal.get("observed_at") if isinstance(temporal, dict) else getattr(temporal, "observed_at", None)

    t0_str = str(t0) if t0 is not None else "unknown"
    sid_str = str(sid) if sid is not None else "unknown"
    t1_str = str(t1) if t1 is not None else "unknown"
    t3_str = str(t3) if t3 is not None else "unknown"

    return (
        STATEMENT_TEMPLATE.replace("<t0>", t0_str)
        .replace("<sid>", sid_str)
        .replace("<t1>", t1_str)
        .replace("<t3>", t3_str)
    )
