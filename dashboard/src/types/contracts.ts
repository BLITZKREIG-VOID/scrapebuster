// Mirrors the canonical response contracts in backend/sb/contracts.py.
export type Decision = 'FAST_PATH' | 'SANDBOX';
export type Layer = 'ORIGIN' | 'EDGE';
export type ComponentStatus = 'ok' | 'down' | 'disabled' | 'unknown' | 'not_checked';
export type CanaryStatus = 'DRAFT' | 'ACTIVE' | 'EXPOSED' | 'OBSERVED';
export type DemoMode = 'live' | 'neutral' | 'golden';
export type DemoPhase = 'READY' | 'RUNNING' | 'COMPLETE' | 'PAUSED' | 'FAILED';

export interface Health {
  status: 'ok' | 'degraded';
  components: Record<string, ComponentStatus>;
}

export interface TrafficEvent {
  seq: number;
  event_id: string;
  ts: string;
  session_id: string;
  client_key: string;
  client_ip: string;
  ip?: string;
  asn?: number | null;
  asn_status?: string;
  ja3_hash?: string | null;
  ja4_hash?: string | null;
  http_version?: string;
  header_order?: string[];
  header_fp?: string;
  tls_source?: string;
  method: string;
  path: string;
  status_code: number;
  user_agent: string;
  stage?: string;
  layer?: string;
  decision: Decision;
  risk_score: number;
  reasons: string[];
  canary_ids?: string[];
  route_class?: string;
}

export interface TrafficEventsResponse {
  events: TrafficEvent[];
  last_seq: number;
}

export interface SessionSummary {
  session_id: string;
  classification: string;
  request_count: number;
  state: string;
  client_ip?: string;
  asset_ratio?: number;
  trust_score?: number;
  first_seen?: string;
  last_seen?: string;
}

export interface SessionDetail extends SessionSummary {
  client_key: string;
  client_ip: string;
  ip?: string;
  asn: number | null;
  asn_status: string;
  ja3_hash: string | null;
  ja4_hash: string | null;
  tls_source: string;
  user_agent: string;
  header_fp: string;
  first_seen: string;
  last_seen: string;
  static_count: number;
  api_count: number;
  asset_ratio: number;
  trust_score?: number;
  ar_classifier_decision?: string;
  confidence_score?: number;
  router_decision?: string;
  decision: Decision;
  risk_score: number;
  reasons: string[];
  pages: string[];
  traps_triggered: string[];
  canaries_exposed: string[];
  event_ids: string[];
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

export interface Publication {
  canary_id: string;
  sha256: string;
  content_version: string;
  published_at: string | null;
  placements: string[];
}

export interface CanaryDetail extends Canary {
  publication: Publication | null;
  exposures: ExposureEvent[];
}

export interface Dataset {
  dataset_id: string;
  role: 'target' | 'control';
  path: string;
  sha256: string;
  records: number;
  ingested_at: string;
}

export interface ProbeResult {
  result_id: string;
  canary_id: string;
  prompt: string;
  retrieved: Record<string, unknown>[];
  response_text: string;
  response_sha256: string;
  latency_ms: number;
  ts: string;
}

export interface ProbeRun {
  probe_id: string;
  target: string;
  status: string;
  dataset_id: string;
  dataset_sha256: string;
  started_at: string;
  finished_at: string | null;
  model: Record<string, unknown>;
  results: ProbeResult[];
}

export interface ProbeRunResponse {
  probe_ids: Record<string, string>;
  case_id: string | null;
}

export interface Finding {
  finding_id: string;
  canary_id: string;
  exact_match: boolean;
  context_match: Record<string, unknown>;
  uniqueness: string;
  temporal: Record<string, unknown>;
  integrity: string;
  control_negative: boolean;
  status: string;
  confidence: string;
}

export interface CaseSummary {
  case_id: string;
  run_id: string;
  created_at: string;
  status: string;
  confidence: string;
  primary_canary_id: string;
}

export interface Case extends CaseSummary {
  session_ids: string[];
  probe_ids: string[];
  findings: Finding[];
  evidence: Record<string, unknown>;
  statement: string;
}

export interface EvidenceFile {
  name: string;
  sha256: string;
  bytes: number;
}

export interface EvidenceManifest {
  case_id: string;
  run_id: string;
  created_at: string;
  files: EvidenceFile[];
  prev_manifest_sha256: string;
  tool_version: string;
  manifest_sha256: string;
}

export interface EvidenceObject extends EvidenceFile {
  local_path: string;
  s3_key: string | null;
  s3_version_id: string | null;
  retain_until: string | null;
}

export interface CaseEvidence {
  manifest: EvidenceManifest;
  objects: EvidenceObject[];
  receipt: Record<string, unknown> | null;
}

export interface EvidenceCheck {
  name: string;
  ok: boolean;
  detail: string;
}

export interface VerifyResult {
  result: 'VALID' | 'TAMPERED';
  checks: EvidenceCheck[];
}

export interface DemoStep {
  id: number;
  name: string;
  status: 'PENDING' | 'RUNNING' | 'PASS' | 'FAIL';
  detail: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface DemoStatus {
  run_id: string | null;
  phase: DemoPhase;
  mode: DemoMode;
  steps: DemoStep[];
}

export interface DemoResetResponse {
  ok: boolean;
  run_id: string;
  checks: { name: string; ok: boolean; detail: string }[];
}

export interface Overview {
  run_id: string;
  counts: Record<Decision, number>;
  ladder?: {
    fast_path?: number;
    sandbox?: number;
    canary_exposed?: number;
    provenance?: number;
    [key: string]: number | undefined;
  };
  sessions_by_class: Record<string, number>;
  canaries: { active: number; exposed: number; observed: number };
  cases: { total: number; detected: number };
  pipeline: { stage: string; status: ComponentStatus }[];
  latest_case: CaseSummary | null;
  total_sessions?: number;
  total_events?: number;
  asset_ratio_avg?: number;
  ledger_valid?: boolean;
  ledger_status?: string;
  ledger_count?: number;
  ledger_head?: string;
}

export interface LedgerBlock {
  seq: number;
  kind: string;
  record: Record<string, unknown>;
  prev_hash: string;
  hash: string;
  ts: string;
}

export interface LedgerInfo {
  result: 'VALID' | 'TAMPERED';
  count: number;
  head: string;
  errors: string[];
  blocks?: LedgerBlock[];
}

export interface RouteBaselineInfo {
  route: string;
  ar_ema: number;
  sample_count: number;
  updated_at: string;
  is_mature: boolean;
}

export interface ClassifierMetrics {
  total_evaluations: number;
  fast_path_count: number;
  sandbox_count: number;
  locked_sandbox_count: number;
  cold_start_count: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  confidence_distribution: Record<string, number>;
}

export interface ClassifierStatus {
  status: string;
  mutation_mode: string;
  alpha: number;
  trust_threshold: number;
  anomaly_streak_threshold: number;
  baseline_min_samples: number;
  total_routes: number;
  matured_routes: number;
  metrics: ClassifierMetrics;
  routes: RouteBaselineInfo[];
}

