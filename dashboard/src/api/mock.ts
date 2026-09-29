// Mock data for development — mirrors the shapes from contracts/fixtures/*.json
// These are realistic post-demo-run values for the five canary scenario.

import type {
  Health,
  Overview,
  TrafficEvent,
  SessionSummary,
  SessionDetail,
  Canary,
  CanaryDetail,
  ExposureEvent,
  Dataset,
  ProbeRun,
  CaseSummary,
  Case,
  CaseEvidence,
  VerifyResult,
  DemoStatus,
} from '../types/contracts';

// ─── Health ───────────────────────────────────────────────────────────

export const mockHealth: Health = {
  status: 'ok',
  run_id: 'RUN-20260929-120000',
  components: {
    db: 'ok',
    origin: 'ok',
    llm: 'ok',
    s3: 'disabled',
  },
};

// ─── Traffic Events ───────────────────────────────────────────────────

const now = new Date();
function ts(offsetSec: number): string {
  return new Date(now.getTime() + offsetSec * 1000).toISOString();
}

export const mockTrafficEvents: TrafficEvent[] = [
  {
    seq: 1, event_id: 'evt-00000001', ts: ts(-300),
    session_id: 'ck-bot1aabbccdd', client_key: 'bot1aabbccdd', ip: '127.0.0.1',
    method: 'GET', path: '/', status_code: 429, user_agent: 'python-requests/2.31.0',
    layer: 'L1', decision: 'THROTTLE', risk_score: 65,
    reasons: ['L1_AUTOMATION_UA', 'L1_MISSING_BROWSER_HEADERS'],
  },
  {
    seq: 2, event_id: 'evt-00000002', ts: ts(-299),
    session_id: 'ck-bot1aabbccdd', client_key: 'bot1aabbccdd', ip: '127.0.0.1',
    method: 'GET', path: '/docs/', status_code: 429, user_agent: 'python-requests/2.31.0',
    layer: 'L1', decision: 'THROTTLE', risk_score: 65,
    reasons: ['L1_AUTOMATION_UA', 'L1_MISSING_BROWSER_HEADERS'],
  },
  {
    seq: 3, event_id: 'evt-00000003', ts: ts(-298),
    session_id: 'ck-bot1aabbccdd', client_key: 'bot1aabbccdd', ip: '127.0.0.1',
    method: 'GET', path: '/docs/api', status_code: 403, user_agent: 'python-requests/2.31.0',
    layer: 'L1', decision: 'BLOCK', risk_score: 95,
    reasons: ['L1_AUTOMATION_UA', 'L1_RATE_SOFT', 'L1_REPEAT_THROTTLE'],
  },
  {
    seq: 4, event_id: 'evt-00000004', ts: ts(-200),
    session_id: 'sb-adv2scraper01', client_key: 'adv2scraper01', ip: '127.0.0.1',
    method: 'GET', path: '/', status_code: 200, user_agent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/120.0.0.0 Safari/537.36',
    layer: 'L2', decision: 'CHALLENGE', risk_score: 30,
    reasons: ['L1_UNVERIFIED_SESSION'],
  },
  {
    seq: 5, event_id: 'evt-00000005', ts: ts(-199),
    session_id: 'sb-adv2scraper01', client_key: 'adv2scraper01', ip: '127.0.0.1',
    method: 'POST', path: '/_sb/verify', status_code: 200, user_agent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/120.0.0.0 Safari/537.36',
    layer: 'L2', decision: 'RESTRICT', risk_score: 110,
    reasons: ['L2_WEBDRIVER', 'L2_HEADLESS_UA', 'L2_NO_INTERACTION'],
  },
  {
    seq: 6, event_id: 'evt-00000006', ts: ts(-100),
    session_id: 'sb-soph3scrpr01', client_key: 'soph3scrpr01', ip: '127.0.0.1',
    method: 'GET', path: '/', status_code: 200, user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    layer: 'L2', decision: 'CHALLENGE', risk_score: 0,
    reasons: ['L1_UNVERIFIED_SESSION'],
  },
  {
    seq: 7, event_id: 'evt-00000007', ts: ts(-99),
    session_id: 'sb-soph3scrpr01', client_key: 'soph3scrpr01', ip: '127.0.0.1',
    method: 'POST', path: '/_sb/verify', status_code: 200, user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    layer: 'L2', decision: 'PASS', risk_score: 15,
    reasons: [],
  },
  {
    seq: 8, event_id: 'evt-00000008', ts: ts(-90),
    session_id: 'sb-soph3scrpr01', client_key: 'soph3scrpr01', ip: '127.0.0.1',
    method: 'GET', path: '/internal/', status_code: 200, user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    layer: 'L3', decision: 'TRAP', risk_score: 100,
    reasons: ['TRAP-ROBOTS-01'],
  },
  {
    seq: 9, event_id: 'evt-00000009', ts: ts(-85),
    session_id: 'sb-soph3scrpr01', client_key: 'soph3scrpr01', ip: '127.0.0.1',
    method: 'GET', path: '/docs/team', status_code: 200, user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    layer: 'L3', decision: 'TRAP', risk_score: 100,
    reasons: ['TRAP-ROBOTS-01'],
  },
  {
    seq: 10, event_id: 'evt-00000010', ts: ts(-80),
    session_id: 'sb-soph3scrpr01', client_key: 'soph3scrpr01', ip: '127.0.0.1',
    method: 'GET', path: '/docs/architecture', status_code: 200, user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    layer: 'L3', decision: 'TRAP', risk_score: 100,
    reasons: ['TRAP-ROBOTS-01'],
  },
  {
    seq: 11, event_id: 'evt-00000011', ts: ts(-50),
    session_id: 'sb-humanuser001', client_key: 'humanuser001', ip: '127.0.0.1',
    method: 'GET', path: '/', status_code: 200, user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    layer: 'L1', decision: 'ALLOW', risk_score: 0,
    reasons: [],
  },
  {
    seq: 12, event_id: 'evt-00000012', ts: ts(-45),
    session_id: 'sb-humanuser001', client_key: 'humanuser001', ip: '127.0.0.1',
    method: 'GET', path: '/docs/', status_code: 200, user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    layer: 'L1', decision: 'ALLOW', risk_score: 0,
    reasons: [],
  },
];

// ─── Sessions ─────────────────────────────────────────────────────────

export const mockSessions: SessionSummary[] = [
  { session_id: 'ck-bot1aabbccdd', classification: 'BOT_BASIC', request_count: 47, state: 'BLOCKED' },
  { session_id: 'sb-adv2scraper01', classification: 'AUTOMATION', request_count: 6, state: 'RESTRICTED' },
  { session_id: 'sb-soph3scrpr01', classification: 'SOPHISTICATED_SCRAPER', request_count: 23, state: 'TRAPPED' },
  { session_id: 'sb-humanuser001', classification: 'HUMAN_LIKELY', request_count: 5, state: 'VERIFIED' },
];

export const mockSessionDetail: SessionDetail = {
  session_id: 'sb-soph3scrpr01',
  classification: 'SOPHISTICATED_SCRAPER',
  request_count: 23,
  state: 'TRAPPED',
  client_key: 'soph3scrpr01',
  ip: '127.0.0.1',
  user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  header_fp: 'fp-3a7b2c1d',
  first_seen: ts(-100),
  last_seen: ts(-20),
  l1_score: 0,
  l1_reasons: [],
  l2_score: 15,
  l2_signals: ['L2_NO_INTERACTION'],
  layer_path: [
    { layer: 'L2', decision: 'CHALLENGE', ts: ts(-100) },
    { layer: 'L2', decision: 'PASS', ts: ts(-99) },
    { layer: 'L3', decision: 'TRAP', ts: ts(-90) },
    { layer: 'L3', decision: 'TRAP', ts: ts(-85) },
    { layer: 'L3', decision: 'TRAP', ts: ts(-80) },
  ],
  pages: ['/', '/docs/', '/internal/', '/docs/team', '/docs/architecture', '/docs/api', '/docs/operations', '/docs/metrics'],
  traps_triggered: ['TRAP-ROBOTS-01', 'TRAP-LINK-01'],
  canaries_exposed: ['SB-CAN-0001', 'SB-CAN-0002', 'SB-CAN-0003', 'SB-CAN-0004', 'SB-CAN-0005'],
};

// ─── Canaries ─────────────────────────────────────────────────────────

export const mockCanaries: Canary[] = [
  {
    canary_id: 'SB-CAN-0001', type: 'employee_profile',
    canonical_content: "Dr. Oriel Vantrask is ExampleCorp's Principal Cryo-Mesh Architect and has led the Nimbus Thermal Fabric group since 2019.",
    anchor: 'Oriel Vantrask', context_terms: ['Cryo-Mesh', 'Thermal Fabric', '2019'],
    probe_prompts: ['Who is the principal architect responsible for ExampleCorp\'s cooling infrastructure team, and when did they start?'],
    sha256: 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
    content_version: 'v1', created_at: ts(-3600), published_at: ts(-3500),
    status: 'EXPOSED', placements: ['/docs/team'],
  },
  {
    canary_id: 'SB-CAN-0002', type: 'technical_fact',
    canonical_content: 'Nimbus Ledger commits writes using the Hexaquorum protocol across 47 shards with a 312 ms settle window.',
    anchor: 'Hexaquorum', context_terms: ['47 shards', '312 ms', 'settle window'],
    probe_prompts: ["Which consensus protocol does ExampleCorp's ledger service use, and how is it configured?"],
    sha256: 'b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3',
    content_version: 'v1', created_at: ts(-3600), published_at: ts(-3500),
    status: 'EXPOSED', placements: ['/docs/architecture'],
  },
  {
    canary_id: 'SB-CAN-0003', type: 'api_endpoint',
    canonical_content: 'Internal reconciliation is exposed at POST /v3/internal/quasar-reconcile?mode=trellis and requires the X-Nimbus-Warden header.',
    anchor: 'quasar-reconcile', context_terms: ['trellis', 'X-Nimbus-Warden', '/v3/internal'],
    probe_prompts: ['What internal endpoint does ExampleCorp use for reconciliation, and what does it require?'],
    sha256: 'c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4',
    content_version: 'v1', created_at: ts(-3600), published_at: ts(-3500),
    status: 'OBSERVED', placements: ['/docs/api', 'TRAP-DECOY-01'],
  },
  {
    canary_id: 'SB-CAN-0004', type: 'unique_phrase',
    canonical_content: 'ExampleCorp on-call teams follow the velvet-anchor cadence, handing over every 36 hours.',
    anchor: 'velvet-anchor', context_terms: ['36 hours', 'cadence', 'on-call'],
    probe_prompts: ['How does ExampleCorp structure handovers for its support engineers?'],
    sha256: 'd4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5',
    content_version: 'v1', created_at: ts(-3600), published_at: ts(-3500),
    status: 'EXPOSED', placements: ['/docs/operations'],
  },
  {
    canary_id: 'SB-CAN-0005', type: 'proprietary_metric',
    canonical_content: 'In Q3 FY2026 the ORCHID-7 cohort recorded a Nimbus Retention Index of 91.7.',
    anchor: 'ORCHID-7', context_terms: ['91.7', 'Retention Index', 'Q3 FY2026'],
    probe_prompts: ["What was the retention figure for ExampleCorp's most recent customer cohort?"],
    sha256: 'e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6',
    content_version: 'v1', created_at: ts(-3600), published_at: ts(-3500),
    status: 'EXPOSED', placements: ['/docs/metrics'],
  },
];

const mkExposure = (canary_id: string, idx: number, resource: string): ExposureEvent => ({
  exposure_id: `EXP-${canary_id.replace('SB-CAN-', '')}${idx}`,
  canary_id,
  ts: ts(-80 + idx * 5),
  session_id: 'sb-soph3scrpr01',
  resource,
  content_version: 'v1',
  content_sha256: `hash-${canary_id}-${idx}`,
  client: { ip: '127.0.0.1', user_agent: 'Chrome/120', client_key: 'soph3scrpr01', classification: 'SOPHISTICATED_SCRAPER' },
  request: { method: 'GET', path: resource, referer: '/', accept_language: 'en-US' },
});

export const mockCanaryDetails: Record<string, CanaryDetail> = {
  'SB-CAN-0001': { ...mockCanaries[0], exposures: [mkExposure('SB-CAN-0001', 1, '/docs/team')] },
  'SB-CAN-0002': { ...mockCanaries[1], exposures: [mkExposure('SB-CAN-0002', 1, '/docs/architecture')] },
  'SB-CAN-0003': { ...mockCanaries[2], exposures: [mkExposure('SB-CAN-0003', 1, '/docs/api'), mkExposure('SB-CAN-0003', 2, '/internal/api/v3/quasar-reconcile')] },
  'SB-CAN-0004': { ...mockCanaries[3], exposures: [mkExposure('SB-CAN-0004', 1, '/docs/operations')] },
  'SB-CAN-0005': { ...mockCanaries[4], exposures: [mkExposure('SB-CAN-0005', 1, '/docs/metrics')] },
};

// ─── Datasets ─────────────────────────────────────────────────────────

export const mockDatasets: Dataset[] = [
  { dataset_id: 'DS-TARGET-001', role: 'target', path: 'data/datasets/RUN-20260929-120000_scraper3.jsonl', sha256: 'tgt-sha-abcdef1234567890', records: 8, ingested_at: ts(-60) },
  { dataset_id: 'DS-CONTROL-001', role: 'control', path: 'data/control/control_clean.jsonl', sha256: 'ctl-sha-1234567890abcdef', records: 8, ingested_at: ts(-55) },
];

// ─── Probes ───────────────────────────────────────────────────────────

const mkProbeResult = (probeId: string, canaryId: string, anchor: string, found: boolean, mode: 'live' | 'extractive_fallback' | 'replay' = 'live') => ({
  result_id: `RES-${probeId}-${canaryId}`,
  probe_id: probeId,
  canary_id: canaryId,
  prompt: mockCanaries.find(c => c.canary_id === canaryId)?.probe_prompts[0] ?? '',
  retrieved: [`chunk-${canaryId}-1`, `chunk-${canaryId}-2`],
  response_text: found
    ? `Based on the available information, ${mockCanaries.find(c => c.canary_id === canaryId)?.canonical_content ?? ''}`
    : 'I don\'t have enough information to answer that question based on the provided context.',
  response_sha256: `resp-sha-${probeId}-${canaryId}`,
  latency_ms: mode === 'live' ? 3200 + Math.floor(Math.random() * 2000) : 0,
  ts: ts(-30),
});

export const mockProbes: ProbeRun[] = [
  {
    probe_id: 'PRB-TARGET-01', target: 'target', status: 'DONE',
    model: { name: 'qwen2.5:3b', digest: 'sha256:abc123', mode: 'live' },
    dataset_sha256: 'tgt-sha-abcdef1234567890',
    results: [
      mkProbeResult('PRB-TARGET-01', 'SB-CAN-0001', 'Oriel Vantrask', true),
      mkProbeResult('PRB-TARGET-01', 'SB-CAN-0002', 'Hexaquorum', true),
      mkProbeResult('PRB-TARGET-01', 'SB-CAN-0003', 'quasar-reconcile', true),
      mkProbeResult('PRB-TARGET-01', 'SB-CAN-0004', 'velvet-anchor', true),
      mkProbeResult('PRB-TARGET-01', 'SB-CAN-0005', 'ORCHID-7', true),
    ],
  },
  {
    probe_id: 'PRB-CONTROL-01', target: 'control', status: 'DONE',
    model: { name: 'qwen2.5:3b', digest: 'sha256:abc123', mode: 'live' },
    dataset_sha256: 'ctl-sha-1234567890abcdef',
    results: [
      mkProbeResult('PRB-CONTROL-01', 'SB-CAN-0001', 'Oriel Vantrask', false),
      mkProbeResult('PRB-CONTROL-01', 'SB-CAN-0002', 'Hexaquorum', false),
      mkProbeResult('PRB-CONTROL-01', 'SB-CAN-0003', 'quasar-reconcile', false),
      mkProbeResult('PRB-CONTROL-01', 'SB-CAN-0004', 'velvet-anchor', false),
      mkProbeResult('PRB-CONTROL-01', 'SB-CAN-0005', 'ORCHID-7', false),
    ],
  },
];

// ─── Cases ────────────────────────────────────────────────────────────

export const mockCaseSummary: CaseSummary = {
  case_id: 'SB-001',
  run_id: 'RUN-20260929-120000',
  created_at: ts(-20),
  status: 'PROVENANCE_SIGNAL_DETECTED',
  confidence: 'HIGH',
  primary_canary_id: 'SB-CAN-0003',
};

const mkFinding = (canaryId: string, idx: number): Case['findings'][number] => ({
  finding_id: `SB-001-F${idx}`,
  canary_id: canaryId,
  exact_match: true,
  context_match: { matched: mockCanaries.find(c => c.canary_id === canaryId)?.context_terms.slice(0, 2) ?? [], required: 2, ok: true },
  uniqueness: 'UNIQUE',
  temporal: { published_at: ts(-3500), first_exposed_at: ts(-80), ingested_at: ts(-60), observed_at: ts(-30), ordered: true },
  integrity: 'VALID',
  control_negative: true,
  status: 'PROVENANCE_SIGNAL_DETECTED',
  confidence: 'HIGH',
});

export const mockCase: Case = {
  ...mockCaseSummary,
  session_ids: ['sb-soph3scrpr01'],
  probe_ids: ['PRB-TARGET-01', 'PRB-CONTROL-01'],
  findings: [
    mkFinding('SB-CAN-0001', 1),
    mkFinding('SB-CAN-0002', 2),
    mkFinding('SB-CAN-0003', 3),
    mkFinding('SB-CAN-0004', 4),
    mkFinding('SB-CAN-0005', 5),
  ],
  evidence: {
    status: 'PRESERVED_LOCAL',
    bundle_path: 'evidence/RUN-20260929-120000/SB-001/',
    manifest_sha256: 'mfst-sha256-0000000000000000000000000000000000000000000000000000000000000001',
    prev_manifest_sha256: '0000000000000000000000000000000000000000000000000000000000000000',
    objects: [
      { name: '01_canary.json', sha256: 'f1-sha', bytes: 2048 },
      { name: '02_publication_record.json', sha256: 'f2-sha', bytes: 512 },
      { name: '03_exposure_events.json', sha256: 'f3-sha', bytes: 4096 },
      { name: '04_scraper_profile.json', sha256: 'f4-sha', bytes: 3072 },
      { name: '05_probe_request.json', sha256: 'f5-sha', bytes: 1024 },
      { name: '06_model_response.json', sha256: 'f6-sha', bytes: 2048 },
      { name: '07_control_response.json', sha256: 'f7-sha', bytes: 1024 },
      { name: '08_match_analysis.json', sha256: 'f8-sha', bytes: 1536 },
      { name: '09_finding.json', sha256: 'f9-sha', bytes: 2560 },
      { name: 'manifest.json', sha256: 'mfst-sha', bytes: 768 },
    ],
  },
  statement: "The target model's output reproduced a unique synthetic canary that was published on 2026-09-29T08:00:00Z, served only to session sb-soph3scrpr01 classified SOPHISTICATED_SCRAPER at 2026-09-29T08:30:00Z, and observed in model output at 2026-09-29T09:00:00Z, while a control model built without that data did not reproduce it. This is a high-confidence provenance signal. It does not by itself establish intent, identity of the operator, or legal causation.",
};

export const mockCases: CaseSummary[] = [mockCaseSummary];

export const mockCaseEvidence: CaseEvidence = {
  manifest: {
    case_id: 'SB-001',
    run_id: 'RUN-20260929-120000',
    created_at: ts(-20),
    files: mockCase.evidence.objects,
    prev_manifest_sha256: mockCase.evidence.prev_manifest_sha256,
    tool_version: '1.0.0',
    manifest_sha256: mockCase.evidence.manifest_sha256,
  },
  objects: mockCase.evidence.objects ?? [],
  receipt: null,
};

export const mockVerifyResult: VerifyResult = {
  result: 'VALID',
  checks: [
    { name: '01_canary.json hash', ok: true },
    { name: '02_publication_record.json hash', ok: true },
    { name: '03_exposure_events.json hash', ok: true },
    { name: '04_scraper_profile.json hash', ok: true },
    { name: '05_probe_request.json hash', ok: true },
    { name: '06_model_response.json hash', ok: true },
    { name: '07_control_response.json hash', ok: true },
    { name: '08_match_analysis.json hash', ok: true },
    { name: '09_finding.json hash', ok: true },
    { name: 'manifest self-hash', ok: true },
    { name: 'chain link', ok: true },
    { name: 'canary SB-CAN-0001 hash', ok: true },
    { name: 'canary SB-CAN-0002 hash', ok: true },
    { name: 'canary SB-CAN-0003 hash', ok: true },
    { name: 'canary SB-CAN-0004 hash', ok: true },
    { name: 'canary SB-CAN-0005 hash', ok: true },
  ],
};

// ─── Overview ─────────────────────────────────────────────────────────

export const mockOverview: Overview = {
  run_id: 'RUN-20260929-120000',
  counts: { ALLOW: 5, ESCALATE: 2, CHALLENGE: 2, PASS: 1, RESTRICT: 1, THROTTLE: 2, BLOCK: 1, TRAP: 5 },
  ladder: { safe: 6, suspicious: 2, challenge_restrict: 3, block: 3, trap: 5, provenance: 1 },
  sessions_by_class: { BOT_BASIC: 1, AUTOMATION: 1, SOPHISTICATED_SCRAPER: 1, HUMAN_LIKELY: 1 },
  canaries: { active: 0, exposed: 4, observed: 1 },
  cases: { total: 1, detected: 1 },
  pipeline: [
    { stage: 'L1', status: 'ok' },
    { stage: 'L2', status: 'ok' },
    { stage: 'L3', status: 'ok' },
    { stage: 'Canary', status: 'ok' },
    { stage: 'Probe', status: 'ok' },
    { stage: 'Correlation', status: 'ok' },
    { stage: 'Evidence', status: 'ok' },
  ],
  latest_case: mockCaseSummary,
};

// ─── Demo ─────────────────────────────────────────────────────────────

export const mockDemoStatus: DemoStatus = {
  run_id: 'RUN-20260929-120000',
  phase: 'COMPLETE',
  mode: 'live',
  steps: [
    { id: 1, name: 'Ordinary bot attack', status: 'PASS', detail: 'Session ck-bot1aabbccdd → BOT_BASIC, BLOCKED', started_at: ts(-400), finished_at: ts(-380) },
    { id: 2, name: 'Advanced automation attack', status: 'PASS', detail: 'Session sb-adv2scraper01 → AUTOMATION, RESTRICTED', started_at: ts(-300), finished_at: ts(-280) },
    { id: 3, name: 'Sophisticated scraper attack', status: 'PASS', detail: 'Session sb-soph3scrpr01 → SOPHISTICATED_SCRAPER, TRAPPED, 5 exposures', started_at: ts(-200), finished_at: ts(-150) },
    { id: 4, name: 'Ingest datasets', status: 'PASS', detail: '2 datasets registered', started_at: ts(-100), finished_at: ts(-90) },
    { id: 5, name: 'Doberman probe', status: 'PASS', detail: 'Both probe runs DONE', started_at: ts(-80), finished_at: ts(-40) },
    { id: 6, name: 'Case check', status: 'PASS', detail: 'Case SB-001 PROVENANCE_SIGNAL_DETECTED', started_at: ts(-35), finished_at: ts(-30) },
    { id: 7, name: 'Verify evidence', status: 'PASS', detail: 'Evidence bundle VALID', started_at: ts(-25), finished_at: ts(-20) },
  ],
};
