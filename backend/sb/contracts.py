from typing import Any, Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: str = "ok"

class TrafficEvent(BaseModel):
    seq: int
    event_id: str
    ts: str
    session_id: str
    client_key: str
    ip: str
    method: str
    path: str
    status_code: int
    user_agent: str
    layer: Literal["L1", "L2", "L3", "ORIGIN"]
    decision: Literal["ALLOW", "ESCALATE", "CHALLENGE", "PASS", "RESTRICT", "THROTTLE", "BLOCK", "TRAP"]
    risk_score: int
    reasons: list[str]

class SessionSummary(BaseModel):
    session_id: str
    classification: str
    request_count: int
    state: str

class SessionDetail(SessionSummary):
    client_key: str
    ip: str
    user_agent: str
    header_fp: str
    first_seen: str
    last_seen: str
    l1_score: int
    l1_reasons: list[str]
    l2_score: int
    l2_signals: list[str]
    layer_path: list[dict[str, Any]]
    pages: list[str]
    traps_triggered: list[str]
    canaries_exposed: list[str]

class ExposureEvent(BaseModel):
    exposure_id: str
    canary_id: str
    ts: str
    session_id: str
    resource: str
    content_version: str
    content_sha256: str
    client: dict[str, Any]
    request: dict[str, Any]

class Canary(BaseModel):
    canary_id: str
    type: str
    canonical_content: str
    anchor: str
    context_terms: list[str]
    probe_prompts: list[str]
    sha256: str
    content_version: str
    created_at: str
    published_at: str | None = None
    status: Literal["DRAFT", "ACTIVE", "EXPOSED", "OBSERVED"]
    placements: list[str]

class Dataset(BaseModel):
    dataset_id: str
    role: Literal["target", "control"]
    path: str
    sha256: str
    records: int
    ingested_at: str

class Finding(BaseModel):
    finding_id: str
    canary_id: str
    exact_match: bool
    context_match: dict[str, Any]
    uniqueness: str
    temporal: dict[str, Any]
    integrity: str
    control_negative: bool
    status: str
    confidence: str

class CaseSummary(BaseModel):
    case_id: str
    run_id: str
    created_at: str
    status: str
    confidence: str
    primary_canary_id: str

class Case(CaseSummary):
    session_ids: list[str]
    probe_ids: list[str]
    findings: list[Finding]
    evidence: dict[str, Any]
    statement: str

class DemoStatus(BaseModel):
    run_id: str
    phase: str
    mode: Literal["live", "golden"]
