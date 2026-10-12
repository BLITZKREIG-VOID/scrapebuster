-- ScrapeBuster Phase 1 Store DDL Schema
-- Application & System State
CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS demo_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Mutable Operational Projections: Traffic Events
CREATE TABLE IF NOT EXISTS traffic_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    ts TEXT NOT NULL,
    session_id TEXT NOT NULL,
    client_key TEXT NOT NULL,
    client_ip TEXT NOT NULL DEFAULT '',
    ip TEXT, -- Backwards compatibility mirror
    asn INTEGER, -- int | null per supervisor correction
    asn_status TEXT DEFAULT 'unavailable',
    ja3_hash TEXT,
    ja4_hash TEXT,
    tls_source TEXT DEFAULT 'none',
    http_version TEXT DEFAULT 'HTTP/1.1',
    header_order TEXT NOT NULL DEFAULT '[]', -- JSON array of raw header names
    header_fp TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INT NOT NULL,
    user_agent TEXT NOT NULL,
    stage TEXT DEFAULT 'offense',
    layer TEXT DEFAULT 'ORIGIN',
    decision TEXT DEFAULT 'SANDBOX',
    risk_score INT DEFAULT 0,
    reasons TEXT DEFAULT '[]', -- JSON array
    canary_ids TEXT DEFAULT '[]', -- JSON array of served canary IDs
    route_class TEXT DEFAULT 'unknown'
);

-- Mutable Operational Projections: Sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    client_key TEXT NOT NULL,
    client_ip TEXT NOT NULL DEFAULT '',
    ip TEXT, -- Backwards compatibility mirror
    asn INTEGER, -- int | null per supervisor correction
    asn_status TEXT DEFAULT 'unavailable',
    ja3_hash TEXT,
    ja4_hash TEXT,
    tls_source TEXT DEFAULT 'none',
    user_agent TEXT NOT NULL,
    header_fp TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    request_count INT DEFAULT 0,
    static_count INT DEFAULT 0,
    api_count INT DEFAULT 0,
    asset_ratio REAL DEFAULT 0.0,
    trust_score REAL DEFAULT 0.0,
    ar_anomaly_streak INT DEFAULT 0,
    locked_sandbox INT DEFAULT 0,
    state TEXT DEFAULT 'SANDBOX',
    classification TEXT DEFAULT 'UNKNOWN',
    decision TEXT DEFAULT 'SANDBOX',
    risk_score INT DEFAULT 0,
    reasons TEXT DEFAULT '[]', -- JSON array
    pages TEXT DEFAULT '[]', -- JSON array
    traps_triggered TEXT DEFAULT '[]', -- JSON array
    canaries_exposed TEXT DEFAULT '[]', -- JSON array
    event_ids TEXT DEFAULT '[]' -- JSON array
);

-- Phase 2 Adaptive AR Classifier: Route Baselines (PRD FR-2.1, FR-2.5)
CREATE TABLE IF NOT EXISTS route_baselines (
    route TEXT PRIMARY KEY,
    ar_ema REAL DEFAULT 0.0,
    sample_count INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- Offense Subsystem: Trap Hits
CREATE TABLE IF NOT EXISTS trap_hits (
    hit_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    session_id TEXT NOT NULL,
    trap_id TEXT NOT NULL,
    trap_type TEXT NOT NULL,
    path TEXT NOT NULL
);

-- Offense Subsystem: Canaries & Publications
CREATE TABLE IF NOT EXISTS canaries (
    canary_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    canonical_content TEXT NOT NULL,
    anchor TEXT NOT NULL,
    context_terms TEXT NOT NULL, -- JSON array
    probe_prompts TEXT NOT NULL, -- JSON array
    sha256 TEXT NOT NULL,
    content_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    published_at TEXT,
    status TEXT NOT NULL,
    placements TEXT NOT NULL -- JSON array
);

CREATE TABLE IF NOT EXISTS publications (
    canary_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    content_version TEXT NOT NULL,
    published_at TEXT NOT NULL,
    placements TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exposures (
    exposure_id TEXT PRIMARY KEY,
    canary_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    session_id TEXT NOT NULL,
    resource TEXT NOT NULL,
    content_version TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    client TEXT NOT NULL,
    request TEXT NOT NULL
);

-- Provenance & Datasets
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    records INT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS probe_runs (
    probe_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    target TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL,
    model TEXT NOT NULL, -- JSON
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS probe_results (
    result_id TEXT PRIMARY KEY,
    probe_id TEXT NOT NULL,
    canary_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    retrieved TEXT NOT NULL,
    response_text TEXT NOT NULL,
    response_sha256 TEXT NOT NULL,
    latency_ms INT NOT NULL,
    ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence TEXT NOT NULL,
    primary_canary_id TEXT,
    session_ids TEXT NOT NULL,
    probe_ids TEXT NOT NULL,
    findings TEXT NOT NULL,
    evidence TEXT NOT NULL,
    statement TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_objects (
    case_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    bytes INT NOT NULL,
    local_path TEXT NOT NULL,
    s3_key TEXT,
    s3_version_id TEXT,
    retain_until TEXT,
    PRIMARY KEY (case_id, name)
);

-- Authoritative Cryptographic Forensic Ledger (Strictly Append-Only)
CREATE TABLE IF NOT EXISTS forensic_ledger (
    seq INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    record TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    ts TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS prevent_ledger_update
BEFORE UPDATE ON forensic_ledger
BEGIN
    SELECT RAISE(ABORT, 'forensic_ledger is append-only: updates prohibited');
END;

CREATE TRIGGER IF NOT EXISTS prevent_ledger_delete
BEFORE DELETE ON forensic_ledger
BEGIN
    SELECT RAISE(ABORT, 'forensic_ledger is append-only: deletes prohibited');
END;

-- Durable Session Canary Bindings & Sequences
CREATE TABLE IF NOT EXISTS session_canary_bindings (
    canary_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    vector TEXT NOT NULL,
    ts TEXT NOT NULL,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_canary_sequences (
    session_id TEXT PRIMARY KEY,
    next_seq INTEGER NOT NULL
);

-- Projections & Cursor Indices
CREATE INDEX IF NOT EXISTS idx_traffic_events_seq ON traffic_events(seq);
CREATE INDEX IF NOT EXISTS idx_traffic_events_session_id ON traffic_events(session_id);
CREATE INDEX IF NOT EXISTS idx_traffic_events_client_ip ON traffic_events(client_ip);
CREATE INDEX IF NOT EXISTS idx_traffic_events_ts ON traffic_events(ts);
CREATE INDEX IF NOT EXISTS idx_traffic_events_asn ON traffic_events(asn);
CREATE INDEX IF NOT EXISTS idx_traffic_events_ja3 ON traffic_events(ja3_hash);

CREATE INDEX IF NOT EXISTS idx_sessions_last_seen ON sessions(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_classification ON sessions(classification);
CREATE INDEX IF NOT EXISTS idx_sessions_client_ip ON sessions(client_ip);
CREATE INDEX IF NOT EXISTS idx_sessions_asn ON sessions(asn);
CREATE INDEX IF NOT EXISTS idx_sessions_ja3 ON sessions(ja3_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_asset_ratio ON sessions(asset_ratio);

CREATE INDEX IF NOT EXISTS idx_canary_bindings_session ON session_canary_bindings(session_id);
CREATE INDEX IF NOT EXISTS idx_ledger_kind ON forensic_ledger(kind);
CREATE INDEX IF NOT EXISTS idx_ledger_ts ON forensic_ledger(ts);

-- Compatibility sync triggers between ip and client_ip
CREATE TRIGGER IF NOT EXISTS sync_traffic_events_ip_insert
AFTER INSERT ON traffic_events
FOR EACH ROW
WHEN (NEW.client_ip = '' OR NEW.client_ip IS NULL) AND NEW.ip IS NOT NULL AND NEW.ip != ''
BEGIN
    UPDATE traffic_events SET client_ip = NEW.ip WHERE seq = NEW.seq;
END;

CREATE TRIGGER IF NOT EXISTS sync_traffic_events_client_ip_insert
AFTER INSERT ON traffic_events
FOR EACH ROW
WHEN (NEW.ip IS NULL OR NEW.ip = '') AND NEW.client_ip != ''
BEGIN
    UPDATE traffic_events SET ip = NEW.client_ip WHERE seq = NEW.seq;
END;

CREATE TRIGGER IF NOT EXISTS sync_sessions_ip_insert
AFTER INSERT ON sessions
FOR EACH ROW
WHEN (NEW.client_ip = '' OR NEW.client_ip IS NULL) AND NEW.ip IS NOT NULL AND NEW.ip != ''
BEGIN
    UPDATE sessions SET client_ip = NEW.ip WHERE session_id = NEW.session_id;
END;

CREATE TRIGGER IF NOT EXISTS sync_sessions_client_ip_insert
AFTER INSERT ON sessions
FOR EACH ROW
WHEN (NEW.ip IS NULL OR NEW.ip = '') AND NEW.client_ip != ''
BEGIN
    UPDATE sessions SET ip = NEW.client_ip WHERE session_id = NEW.session_id;
END;

