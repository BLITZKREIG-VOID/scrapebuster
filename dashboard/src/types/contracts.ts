// ScapeBusters Dashboard — TypeScript contracts
// Mirrors backend/sb/contracts.py and master plan §16.
// TODO sync at M0: re-verify against contracts-v1 tag

// ─── Enums (fixed contract) ───────────────────────────────────────────

export type Decision =
  | 'ALLOW'
  | 'ESCALATE'
  | 'CHALLENGE'
  | 'PASS'
  | 'RESTRICT'
  | 'THROTTLE'
  | 'BLOCK'
  | 'TRAP';

export type Layer = 'L1' | 'L2' | 'L3' | 'ORIGIN';

export type Classification =
  | 'BOT_BASIC'
  | 'AUTOMATION'
  | 'SOPHISTICATED_SCRAPER'
  | 'HUMAN_LIKELY'
  | 'UNKNOWN';

export type SessionState =
  | 'NEW'
  | 'VERIFIED'
  | 'ESCALATED'
  | 'RESTRICTED'
  | 'THROTTLED'
  | 'BLOCKED'
  | 'TRAPPED';

export type CanaryStatus = 'DRAFT' | 'ACTIVE' | 'EXPOSED' | 'OBSERVED';

export type CaseStatus =
  | 'PROVENANCE_SIGNAL_DETECTED'
  | 'PARTIAL_SIGNAL'
  | 'INCONCLUSIVE'
  | 'NO_SIGNAL';

export type ModelMode = 'live' | 'extractive_fallback' | 'replay';

export type DemoMode = 'live' | 'golden';

// ─── Health ───────────────────────────────────────────────────────────

export interface HealthComponents {
  db: 'ok' | 'down';
  origin: 'ok' | 'down';
  llm: 'ok' | 'down' | 'fallback';
  s3: 'ok' | 'disabled' | 'down';
}

export interface Health {
  status: 'ok' | 'degraded';
  run_id?: string;
  components?: HealthComponents;
}

// ─── Traffic ──────────────────────────────────────────────────────────

export interface TrafficEvent {
  seq: number;
  event_id: string;
  ts: string;
  session_id: string;
  client_key: string;
  ip: string;
  method: string;
  path: string;
  status_code: number;
  user_agent: string;
  layer: Layer;
  decision: Decision;
  risk_score: number;
  reasons: string[];
}

export interface TrafficEventsResponse {
  events: TrafficEvent[];
  last_seq: number;
}

// ─── Sessions ─────────────────────────────────────────────────────────

export interface SessionSummary {
  session_id: string;
  classification: string;
  request_count: number;
  state: string;
}

export interface LayerPathEntry {
  layer: Layer;
  decision: Decision;
  ts: string;
}

export interface SessionDetail extends SessionSummary {
  client_key: string;
  ip: string;
  user_agent: string;
  header_fp: string;
  first_seen: string;
  last_seen: string;
  l1_score: number;
  l1_reasons: string[];
  l2_score: number;
  l2_signals: string[];
  layer_path: LayerPathEntry[];
  pages: string[];
  traps_triggered: string[];
  canaries_exposed: string[];
}

// ─── Canaries ─────────────────────────────────────────────────────────

export interface Canary {
  canary_id: string;
  type: string;
  canonical_content: string;
  anchor: string;
  context_terms: string[];
  probe_prompts: string[];
  sha256: string;
  content_version: string;
  created_at: string;
  published_at: string | null;
  status: CanaryStatus;
  placements: string[];
}

export interface ExposureEvent {
  exposure_id: string;
  canary_id: string;
  ts: string;
  session_id: string;
  resource: string;
  content_version: string;
  content_sha256: string;
  client: Record<string, unknown>;
  request: Record<string, unknown>;
}

export interface CanaryDetail extends Canary {
  publication?: Record<string, unknown>;
  exposures: ExposureEvent[];
}

// ─── Datasets ─────────────────────────────────────────────────────────

export interface Dataset {
  dataset_id: string;
  role: 'target' | 'control';
  path: string;
  sha256: string;
  records: number;
  ingested_at: string;
}

// ─── Probes ───────────────────────────────────────────────────────────

export interface ProbeResult {
  result_id: string;
  probe_id: string;
  canary_id: string;
  prompt: string;
  retrieved: string[];
  response_text: string;
  response_sha256: string;
  latency_ms: number;
  ts: string;
}

export interface ProbeModel {
  name: string;
  digest: string;
  mode: ModelMode;
}

export interface ProbeRun {
  probe_id: string;
  target: string;
  status: string;
  model: ProbeModel;
  dataset_sha256: string;
  results: ProbeResult[];
}

// ─── Findings ─────────────────────────────────────────────────────────

export interface ContextMatch {
  matched: string[];
  required: number;
  ok: boolean;
}

export interface Temporal {
  published_at: string;
  first_exposed_at: string;
  ingested_at: string;
  observed_at: string;
  ordered: boolean;
}

export interface Finding {
  finding_id: string;
  canary_id: string;
  exact_match: boolean;
  context_match: ContextMatch;
  uniqueness: string;
  temporal: Temporal;
  integrity: string;
  control_negative: boolean;
  status: string;
  confidence: string;
}

// ─── Cases ────────────────────────────────────────────────────────────

export interface CaseSummary {
  case_id: string;
  run_id: string;
  created_at: string;
  status: string;
  confidence: string;
  primary_canary_id: string;
}

export interface EvidenceObject {
  name: string;
  sha256: string;
  bytes: number;
  local_path?: string;
  s3_key?: string;
  s3_version_id?: string;
  retain_until?: string;
}

export interface EvidenceSummary {
  status: string;
  bundle_path?: string;
  manifest_sha256?: string;
  prev_manifest_sha256?: string;
  objects?: EvidenceObject[];
  s3_bucket?: string;
  retain_until?: string;
}

export interface Case extends CaseSummary {
  session_ids: string[];
  probe_ids: string[];
  findings: Finding[];
  evidence: EvidenceSummary;
  statement: string;
}

export interface VerifyCheck {
  name: string;
  ok: boolean;
  detail?: string;
}

export interface VerifyResult {
  result: 'VALID' | 'TAMPERED';
  checks: VerifyCheck[];
}

export interface CaseEvidence {
  manifest: Record<string, unknown>;
  objects: EvidenceObject[];
  receipt: Record<string, unknown> | null;
}

// ─── Demo ─────────────────────────────────────────────────────────────

export interface DemoStep {
  id: number;
  name: string;
  status: 'PENDING' | 'RUNNING' | 'PASS' | 'FAIL';
  detail?: string;
  started_at?: string;
  finished_at?: string;
}

export interface DemoStatus {
  run_id: string;
  phase: string;
  mode: DemoMode;
  steps?: DemoStep[];
}

// ─── Overview ─────────────────────────────────────────────────────────

export interface OverviewLadder {
  safe: number;
  suspicious: number;
  challenge_restrict: number;
  block: number;
  trap: number;
  provenance: number;
}

export interface PipelineStage {
  stage: string;
  status: 'ok' | 'pending' | 'active' | 'error';
}

export interface Overview {
  run_id: string;
  counts: Record<Decision, number>;
  ladder: OverviewLadder;
  sessions_by_class: Record<string, number>;
  canaries: { active: number; exposed: number; observed: number };
  cases: { total: number; detected: number };
  pipeline: PipelineStage[];
  latest_case: CaseSummary | null;
}
