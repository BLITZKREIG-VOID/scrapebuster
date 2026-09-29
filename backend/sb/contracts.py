"""Canonical API response contracts shared by backend, E2E, and dashboard.

Nullable fields represent information that is legitimately unavailable at the
time of a response (for example a run not yet created or optional S3 metadata).
Dynamic finding details and model metadata remain mappings because their keys
are producer/model-specific; the containing response shapes are still frozen.
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

ComponentStatus = Literal["ok", "down", "disabled", "unknown", "not_checked"]
Decision = Literal["ALLOW", "ESCALATE", "CHALLENGE", "PASS", "RESTRICT", "THROTTLE", "BLOCK", "TRAP"]


class Health(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    components: dict[str, ComponentStatus]


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
    decision: Decision
    risk_score: int
    reasons: list[str]


class TrafficEvents(BaseModel):
    events: list[TrafficEvent]
    last_seq: int


class SessionSummary(BaseModel):
    session_id: str
    classification: str
    request_count: int
    state: str


class LayerPathEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    layer: str
    decision: str
    ts: str | None = None


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
    layer_path: list[LayerPathEntry]
    pages: list[str]
    traps_triggered: list[str]
    canaries_exposed: list[str]


class SessionList(BaseModel):
    sessions: list[SessionSummary]


class PipelineStage(BaseModel):
    stage: str
    status: ComponentStatus


class DecisionCounts(BaseModel):
    model_config = ConfigDict(extra="allow")

    ALLOW: int = 0
    ESCALATE: int = 0
    CHALLENGE: int = 0
    PASS: int = 0
    RESTRICT: int = 0
    THROTTLE: int = 0
    BLOCK: int = 0
    TRAP: int = 0


class LadderCounts(BaseModel):
    safe: int
    suspicious: int
    challenge_restrict: int
    block: int
    trap: int
    provenance: int


class CanaryCounts(BaseModel):
    active: int
    exposed: int
    observed: int


class CaseCounts(BaseModel):
    total: int
    detected: int


class CaseSummary(BaseModel):
    case_id: str
    run_id: str
    created_at: str
    status: str
    confidence: str
    primary_canary_id: str


class Overview(BaseModel):
    run_id: str
    counts: DecisionCounts
    ladder: LadderCounts
    sessions_by_class: dict[str, int]
    canaries: CanaryCounts
    cases: CaseCounts
    pipeline: list[PipelineStage]
    latest_case: CaseSummary | None = None


class ExposureEvent(BaseModel):
    exposure_id: str
    canary_id: str
    ts: str
    session_id: str
    resource: str
    content_version: str
    content_sha256: str
    # These capture heterogeneous request/session objects; absent context
    # attributes are serialized as null, so retain the producer's map shape.
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


class Publication(BaseModel):
    canary_id: str
    sha256: str
    content_version: str
    published_at: str | None = None
    placements: list[str]


class CanaryDetail(Canary):
    publication: Publication | None = None
    exposures: list[ExposureEvent] = Field(default_factory=list)


class CanariesResponse(BaseModel):
    canaries: list[Canary]


class Dataset(BaseModel):
    dataset_id: str
    role: Literal["target", "control"]
    path: str
    sha256: str
    records: int
    ingested_at: str


class DatasetsResponse(BaseModel):
    datasets: list[Dataset]


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str


class ProbeResult(BaseModel):
    result_id: str
    canary_id: str
    prompt: str
    retrieved: list[dict[str, Any]]
    response_text: str
    response_sha256: str
    latency_ms: int
    ts: str


class ProbeRun(BaseModel):
    probe_id: str
    target: str
    status: str
    dataset_id: str
    dataset_sha256: str
    started_at: str
    finished_at: str | None = None
    model: dict[str, Any]
    results: list[ProbeResult] = Field(default_factory=list)


class ProbeListResponse(BaseModel):
    probes: list[ProbeRun]


class ProbeRunResponse(BaseModel):
    probe_ids: dict[str, str]
    case_id: str | None = None


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


class Case(CaseSummary):
    session_ids: list[str]
    probe_ids: list[str]
    findings: list[Finding]
    evidence: dict[str, Any]
    statement: str


class CaseSummaries(RootModel[list[CaseSummary]]):
    """The cases collection is intentionally a raw JSON array in the API."""


class EvidenceFile(BaseModel):
    name: str
    sha256: str
    bytes: int


class EvidenceManifest(BaseModel):
    case_id: str
    run_id: str
    created_at: str
    files: list[EvidenceFile]
    prev_manifest_sha256: str
    tool_version: str
    manifest_sha256: str


class EvidenceObject(BaseModel):
    name: str
    sha256: str
    bytes: int
    local_path: str
    s3_key: str | None = None
    s3_version_id: str | None = None
    retain_until: str | None = None


class CaseEvidenceResponse(BaseModel):
    manifest: EvidenceManifest
    objects: list[EvidenceObject]
    receipt: dict[str, Any] | None = None


class EvidenceCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class EvidenceVerification(BaseModel):
    result: Literal["VALID", "TAMPERED"]
    checks: list[EvidenceCheck]


class DemoStep(BaseModel):
    id: int
    name: str
    status: Literal["PENDING", "RUNNING", "PASS", "FAIL"]
    detail: str
    started_at: str | None = None
    finished_at: str | None = None


class DemoStatus(BaseModel):
    run_id: str | None = None
    phase: Literal["READY", "RUNNING", "COMPLETE", "PAUSED", "FAILED"]
    mode: Literal["live", "golden"]
    steps: list[DemoStep]


class DemoResetCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class DemoResetResponse(BaseModel):
    ok: bool
    run_id: str
    checks: list[DemoResetCheck]
