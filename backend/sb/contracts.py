from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime

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
    reasons: List[str]

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
    l1_reasons: List[str]
    l2_score: int
    l2_signals: List[str]
    layer_path: List[Dict[str, Any]]
    pages: List[str]
    traps_triggered: List[str]
    canaries_exposed: List[str]

class ExposureEvent(BaseModel):
    exposure_id: str
    canary_id: str
    ts: str
    session_id: str
    resource: str
    content_version: str
    content_sha256: str
    client: Dict[str, Any]
    request: Dict[str, Any]

class Canary(BaseModel):
    canary_id: str
    type: str
    canonical_content: str
    anchor: str
    context_terms: List[str]
    probe_prompts: List[str]
    sha256: str
    content_version: str
    created_at: str
    published_at: Optional[str] = None
    status: Literal["DRAFT", "ACTIVE", "EXPOSED", "OBSERVED"]
    placements: List[str]

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
    context_match: Dict[str, Any]
    uniqueness: str
    temporal: Dict[str, Any]
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
    session_ids: List[str]
    probe_ids: List[str]
    findings: List[Finding]
    evidence: Dict[str, Any]
    statement: str

class DemoStatus(BaseModel):
    run_id: str
    phase: str
    mode: Literal["live", "golden"]
