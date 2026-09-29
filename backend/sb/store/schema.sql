CREATE TABLE demo_state   (key TEXT PRIMARY KEY, value TEXT);                 -- run_id, phase
CREATE TABLE traffic_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE, ts TEXT,  session_id TEXT, client_key TEXT, ip TEXT, method TEXT, path TEXT, status_code INT, user_agent TEXT,  header_fp TEXT, layer TEXT, decision TEXT, risk_score INT, reasons TEXT /*json*/);
CREATE TABLE sessions (session_id TEXT PRIMARY KEY, client_key TEXT, ip TEXT, user_agent TEXT, header_fp TEXT,  first_seen TEXT, last_seen TEXT, request_count INT, state TEXT, classification TEXT,  l1_score INT, l1_reasons TEXT, l2_score INT, l2_signals TEXT, layer_path TEXT, pages TEXT,  traps_triggered TEXT, canaries_exposed TEXT, block_until TEXT);
CREATE TABLE trap_hits (hit_id TEXT PRIMARY KEY, ts TEXT, session_id TEXT, trap_id TEXT, trap_type TEXT, path TEXT);
CREATE TABLE canaries (canary_id TEXT PRIMARY KEY, type TEXT, canonical_content TEXT, anchor TEXT,  context_terms TEXT, probe_prompts TEXT, sha256 TEXT, content_version TEXT, created_at TEXT,  published_at TEXT, status TEXT, placements TEXT);
CREATE TABLE publications (canary_id TEXT PRIMARY KEY, sha256 TEXT, content_version TEXT, published_at TEXT, placements TEXT);
CREATE TABLE exposures (exposure_id TEXT PRIMARY KEY, canary_id TEXT, ts TEXT, session_id TEXT, resource TEXT,  content_version TEXT, content_sha256 TEXT, client TEXT, request TEXT);
CREATE TABLE datasets (dataset_id TEXT PRIMARY KEY, role TEXT, path TEXT, sha256 TEXT, records INT, ingested_at TEXT);
CREATE TABLE probe_runs (probe_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, target TEXT,  dataset_id TEXT, dataset_sha256 TEXT, model TEXT /*json name,digest,mode*/, status TEXT);
CREATE TABLE probe_results (result_id TEXT PRIMARY KEY, probe_id TEXT, canary_id TEXT, prompt TEXT,  retrieved TEXT, response_text TEXT, response_sha256 TEXT, latency_ms INT, ts TEXT);
CREATE TABLE cases (case_id TEXT PRIMARY KEY, run_id TEXT, created_at TEXT, status TEXT, confidence TEXT,  primary_canary_id TEXT, session_ids TEXT, probe_ids TEXT, findings TEXT, evidence TEXT, statement TEXT);
CREATE TABLE evidence_objects (case_id TEXT, name TEXT, sha256 TEXT, bytes INT, local_path TEXT,  s3_key TEXT, s3_version_id TEXT, retain_until TEXT, PRIMARY KEY (case_id, name));
