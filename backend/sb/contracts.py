"""Canonical API response contracts shared by backend, E2E, and dashboard.

Nullable fields represent information that is legitimately unavailable at the
time of a response (for example a run not yet created or optional S3 metadata).
Dynamic finding details and model metadata remain mappings because their keys
are producer/model-specific; the containing response shapes are still frozen.
"""
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

ComponentStatus = Literal["ok", "down", "disabled", "unknown", "not_checked"]
Decision = Literal["FAST_PATH", "SANDBOX"]


class Health(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    components: dict[str, ComponentStatus]


class TrafficEvent(BaseModel):
    seq: int
    event_id: str
    ts: str
    session_id: str
    client_key: str
    client_ip: str
    ip: str | None = None
    asn: int | None = None
    asn_status: str = "unavailable"
    ja3_hash: str | None = None
    ja4_hash: str | None = None
    http_version: str = "HTTP/1.1"
    header_order: list[str] = Field(default_factory=list)
    header_fp: str = ""
    tls_source: str = "none"
    method: str
    path: str
    status_code: int
    user_agent: str
    stage: str | None = "offense"
    layer: str | None = "ORIGIN"
    decision: Decision = "SANDBOX"
    risk_score: int = 0
    reasons: list[str] = Field(default_factory=list)
    canary_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def populate_phase1_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "client_ip" not in data and "ip" in data:
                data["client_ip"] = data["ip"]
            elif "ip" not in data and "client_ip" in data:
                data["ip"] = data["client_ip"]
            if "asn" in data and data["asn"] is not None:
                try:
                    data["asn"] = int(data["asn"])
                except (ValueError, TypeError):
                    data["asn"] = None
            for list_field in ("header_order", "reasons", "canary_ids"):
                val = data.get(list_field)
                if isinstance(val, str):
                    try:
                        data[list_field] = json.loads(val)
                    except Exception:
                        data[list_field] = []
        return data


class TrafficEvents(BaseModel):
    events: list[TrafficEvent]
    last_seq: int


class SessionSummary(BaseModel):
    session_id: str
    classification: str = "UNKNOWN"
    request_count: int = 0
    state: str = "SANDBOX"
    client_ip: str | None = None
    asset_ratio: float = 0.0
    trust_score: float = 0.0


class SessionDetail(SessionSummary):
    client_key: str = ""
    client_ip: str
    ip: str | None = None
    asn: int | None = None
    asn_status: str = "unavailable"
    ja3_hash: str | None = None
    ja4_hash: str | None = None
    tls_source: str = "none"
    user_agent: str = ""
    header_fp: str = ""
    first_seen: str = ""
    last_seen: str = ""
    static_count: int = 0
    api_count: int = 0
    asset_ratio: float = 0.0
    trust_score: float = 0.0
    ar_classifier_decision: str | None = None
    confidence_score: float | None = None
    router_decision: str | None = None
    decision: Decision = "SANDBOX"
    risk_score: int = 0
    reasons: list[str] = Field(default_factory=list)
    pages: list[str] = Field(default_factory=list)
    traps_triggered: list[str] = Field(default_factory=list)
    canaries_exposed: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def populate_phase1_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "client_ip" not in data and "ip" in data:
                data["client_ip"] = data["ip"]
            elif "ip" not in data and "client_ip" in data:
                data["ip"] = data["client_ip"]
            if "asn" in data and data["asn"] is not None:
                try:
                    data["asn"] = int(data["asn"])
                except (ValueError, TypeError):
                    data["asn"] = None
            for list_field in ("reasons", "pages", "traps_triggered", "canaries_exposed", "event_ids"):
                val = data.get(list_field)
                if isinstance(val, str):
                    try:
                        data[list_field] = json.loads(val)
                    except Exception:
                        data[list_field] = []
        return data


class SessionList(BaseModel):
    sessions: list[SessionSummary]


class RouteBaselineInfo(BaseModel):
    route: str
    ar_ema: float
    sample_count: int
    updated_at: str
    is_mature: bool = False


class ClassifierMetrics(BaseModel):
    total_evaluations: int = 0
    fast_path_count: int = 0
    sandbox_count: int = 0
    locked_sandbox_count: int = 0
    cold_start_count: int = 0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    confidence_distribution: dict[str, int] = Field(default_factory=dict)


class ClassifierStatus(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    mutation_mode: str = "adaptive"
    alpha: float = 0.2
    trust_threshold: float = 70.0
    anomaly_streak_threshold: int = 20
    baseline_min_samples: int = 10
    total_routes: int = 0
    matured_routes: int = 0
    metrics: ClassifierMetrics = Field(default_factory=ClassifierMetrics)
    routes: list[RouteBaselineInfo] = Field(default_factory=list)


class PipelineStage(BaseModel):
    stage: str
    status: ComponentStatus


class DecisionCounts(BaseModel):
    model_config = ConfigDict(extra="allow")

    FAST_PATH: int = 0
    SANDBOX: int = 0


class LadderCounts(BaseModel):
    model_config = ConfigDict(extra="allow")

    fast_path: int = 0
    sandbox: int = 0
    canary_exposed: int = 0
    provenance: int = 0


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
    total_sessions: int = 0
    total_events: int = 0
    asset_ratio_avg: float = 0.0
    ledger_valid: bool = True
    ledger_status: str = "VALID"
    ledger_count: int = 0
    ledger_head: str = ""


class LedgerBlock(BaseModel):
    seq: int
    kind: str
    record: dict[str, Any]
    prev_hash: str
    hash: str
    ts: str


class LedgerVerification(BaseModel):
    result: Literal["VALID", "TAMPERED"]
    count: int
    head: str
    errors: list[str] = Field(default_factory=list)
    blocks: list[LedgerBlock] = Field(default_factory=list)


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
    phase: Literal["READY", "RUNNING", "COMPLETE", "PAUSED", "FAILED"] = "READY"
    mode: str = "live"
    steps: list[DemoStep] = Field(default_factory=list)


class DemoResetCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class DemoResetResponse(BaseModel):
    ok: bool
    run_id: str
    checks: list[DemoResetCheck]


class KBQuery(BaseModel):
    query: str
    top_k: int = 5
    filters: dict[str, str] = Field(default_factory=dict)
    include_content: bool = True
    session_id: str | None = None


class KBQueryResponse(BaseModel):
    query: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    total_found: int
    query_time_ms: float
    fallback_used: bool = False


class KBIngestRequest(BaseModel):
    title: str
    content: str
    source: str
    doc_type: str
    metadata: dict[str, str] = Field(default_factory=dict)
    chunk_size: int = 500
    chunk_overlap: int = 50


class KBIngestResponse(BaseModel):
    doc_id: str
    chunks_created: int
    status: str


class KBStats(BaseModel):
    total_documents: int
    total_chunks: int
    total_vectors: int
    storage_size_bytes: int
    last_updated: str


class CallbackEvent(BaseModel):
    callback_id: str
    canary_id: str | None = None
    session_id: str | None = None
    token_verified: bool = False
    binding_value: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    ts: str


class HoneyKeyEvent(BaseModel):
    event_id: str
    key_id: str
    key_value: str
    source_url: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    ts: str
