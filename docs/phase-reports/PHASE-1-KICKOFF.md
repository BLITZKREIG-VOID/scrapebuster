# ScrapeBuster v3 Pure Layer 3 Full Offense — Phase 1 Kickoff & Interface Contracts

- **Document Status**: READY / PUBLISHED (Authoritative Phase 1 kickoff record; implementation edits strictly deferred until supervisor reviews and dispatches worker streams)
- **Phase**: Phase 1 (Milestone 1 / FR1.1–FR1.5: Passive Fingerprinting, Telemetry Tap, Durable Session State & Live Observability)
- **Workstream Owner**: Worker 5 (`@w5` Packaging, QA, Benchmark, Environment, Governance & Integration)
- **Worker Worktree Path**: `C:\Users\kashy\orca\workspaces\scrapebuster\phase1-w5-kickoff`
- **Worker Branch**: `phase1/w5-qa`
- **Parent Baseline Git Commit**: `3611b0eb0e85bad559b4690bce8adbb5cbc95539` (Accepted Phase 0 main, tree `007eb43290c7d979d17c57ee9fff646252a534a5`)
- **Agent Provider / Dispatch Model**: Antigravity Gemini (model/version UNKNOWN (null); never claim Flash 3.8)
- **Authoritative Specification**: User-approved `ScrapeBuster_L3_Full_Offense_PRD.md` v3.0 (Milestone 1, FR1.1–FR1.5) and Eight-Phase Master Plan Phase 1.
- **Forbidden Tokens & PRD Policy**: Literal PRD text and legacy forbidden strings are strictly omitted to maintain zero forbidden tokens outside `.git`. Requirements are cited strictly by PRD milestone and formal section identifiers. Phase 0 full-tree grep guard is fully preserved.

---

## 1. Architectural Vision: Pure Layer 3 Full Offense (Phase 1 Scope)

In Phase 0, ScrapeBuster eliminated all legacy blocking and challenge mechanisms, established a pure sandboxed reverse proxy pipeline, demolished 135 obsolete assets, and deployed an append-only cryptographic forensic ledger with 160 passing tests.

Phase 1 establishes the **Passive Telemetry Tap, Fingerprinting, and Durable Session Subsystem** per PRD Milestone 1 (FR1.1 through FR1.5):
1. **Reverse Proxy Configuration & Request Context (FR1.1)**:
   - Transparent reverse proxy forwarding and dual-origin routing with sandboxed response mutation.
   - Canonical `RequestContext` with IP (`ctx.ip`), headers, path, method, user-agent, and client key.
2. **Passive Client Fingerprinting (FR1.2)**:
   - Passive inspection for client IP, offline ASN (`int | None`), TLS fingerprint (JA3/JA4), and HTTP/2 order.
   - TLS Truth: Genuine local ClientHello capture; NULL for plaintext. Untrusted client headers stripped at edge.
3. **Durable Session State & 7-Tuple Tracking (FR1.3)**:
   - Server-side session tracking establishes durable session 7-tuple: `(session_id, client_ip, asn, ja3_hash, asset_ratio, first_seen, last_seen)`.
   - Persisted to SQLite operational projections and mirrored as immutable background snapshots in ledger.
4. **Asynchronous Background Persistence & Tap Latency (FR1.4)**:
   - Inbound traffic events and session updates frozen and queued via non-blocking queue; p95 added latency < 5ms at 500 rps.
   - Background persistence never blocks reverse proxy request path. High-throughput read models and live feed.
5. **Rolling Asset Ratio Tracking (FR1.5)**:
   - Rolling tracking: `asset_ratio = static_count / max(1, api_count)`.
   - Distinguishes human browser behavior from scraper bursts. Documents not counted as API unless classified.
6. **No Adaptive EMA or Router in Phase 1**:
   - Adaptive routing and exponential moving average (EMA) score filtering are deferred to Phase 2.
   - In Phase 1, **every inbound origin request remains in SANDBOX mode** and undergoes unconditional eligible HTML/JSON mutation. No bypass flags, fake fast-paths, or premature mitigations.

---

## 2. Shared File Ownership and Coordination Policy

To prevent merge conflicts and coordination deadlocks across the five concurrent worker streams, file ownership is strictly partitioned. Exactly **one owner** is assigned per shared file; all other workers consume the module strictly through public APIs and defined contracts.

### 2.1 Shared File Ownership Matrix
| File Path | Sole Owner | Permitted Action by Owner | Consumer Streams (W1–W5) |
|---|---|---|---|
| `backend/sb/config.py` | **Worker 1 (W1)** | Defines environment configuration, parsing, and dual-origin validation. | W2, W3, W4, W5: Read-only import and consumer. |
| `backend/sb/main.py` | **Worker 1 (W1)** | Mounts routers, registers lifespan hooks, manages server startup/shutdown. | W2, W3, W4, W5: Provide modular routers/hooks; do not edit `main.py`. |
| `backend/sb/store/schema.sql` | **Worker 3 (W3)** | Authors and updates DDL schema definitions, triggers, and indices. | W1, W2, W4, W5: Consume via W3 store interfaces and migrations. |
| `.github/CODEOWNERS` | **Worker 5 (W5)** | Updates ownership rules for Phase 1 modules. | W1–W4: Obey governance rules. |
| `Makefile` | **Worker 5 (W5)** | Updates build targets, test commands, and quality gates. | W1–W4: Read-only targets. |
| `.env.example` | **Worker 5 (W5)** | Documents environment configuration matrix. | W1–W4: Provide variable specs to W5. |

### 2.2 Branching and Integration Sequence
```
[phase1/w1-edge]       ──┐
[phase1/w2-offense]    ──┤
[phase1/w3-provenance] ──┼──> [phase1-integration] ──(Independent @verifier Gate)──> [main]
[phase1/w4-dashboard]  ──┤
[phase1/w5-qa]         ──┘
```

1. **Isolation**: Sibling workers operate strictly in isolated branches branched off accepted `main` (`3611b0eb0e85bad559b4690bce8adbb5cbc95539`):
   - `phase1/w1-edge`: Worker 1
   - `phase1/w2-offense`: Worker 2
   - `phase1/w3-provenance`: Worker 3
   - `phase1/w4-dashboard`: Worker 4
   - `phase1/w5-qa`: Worker 5
2. **Merge Sequence into `phase1-integration`**:
   - **Step 1 (W3)**: Store schema DDL, atomic batch ledger, session/traffic persistence.
   - **Step 2 (W1)**: Edge context enrichment, TLS adapter, ASN lookup, background telemetry task.
   - **Step 3 (W2)**: Canonical canary bindings, stamping helpers, contract adapters.
   - **Step 4 (W4)**: API read models, contract schemas, dashboard live feeds.
   - **Step 5 (W5)**: Integrated test suite, benchmark harness, docs, final verification report.
3. **No Mid-Flight Builds or Formats**: Workers do NOT run mid-flight linters, formatters, or exploratory test sweeps. Verification is performed in ONE bounded execution batch on frozen code.
4. **Independent Gate**: Merging `phase1-integration` into `main` occurs strictly after independent `@verifier` evaluation.

---

## 3. Five Worker Task Cards

### Task Card W1: Edge Pipeline, Request Context, TLS Adapter, ASN & Background Telemetry
- **Stream**: Worker 1 (`@w1` / `@anirudh`)
- **Owned Modules**:
  - `backend/sb/edge/context.py`
  - `backend/sb/edge/pipeline.py`
  - `backend/sb/edge/proxy.py`
  - `backend/sb/edge/session.py`
  - `backend/sb/edge/tls.py` (new)
  - `backend/sb/edge/asn.py` (new)
  - `backend/sb/edge/telemetry.py` (new)
  - `backend/sb/config.py` (sole owner)
  - `backend/sb/main.py` (sole owner)
- **Scope & Deliverables**:
  1. **Enriched Request Context (`RequestContext`)**:
     - Extract `client_ip` (handling loopback, IPv4/IPv6, and trusted proxy forwarding).
     - Extract raw User-Agent string.
     - Extract HTTP protocol version (`HTTP/1.1` vs `HTTP/2`).
     - Capture raw header ordering (`header_order: list[str]`) and calculate canonical header fingerprint (`header_fp`).
     - Extract or assign `session_id` using deterministic opaque server-side hashing: `hashlib.sha256(f"{ip}|{user_agent}|{ja3_hash}".encode()).hexdigest()[:16]`.
     - Classify request target: `is_static` (e.g. `.js`, `.css`, `.png`, `/static/`) vs `is_api` (e.g. `/api/`, JSON endpoints).
  2. **TLS Termination & Capture Adapter (`sb.edge.tls`)**:
     - Genuine local TLS capture: Extract actual ClientHello metadata (ciphers, extensions, elliptic curves, point formats) when terminating TLS.
     - Compute standard MD5 JA3 hash (`ja3_hash`) and JA4 string (`ja4_hash`).
     - **TLS Truth**: If connection is plaintext HTTP, store `NULL` for `ja3_hash` and `ja4_hash`, with explicit `tls_source: "none"`. Never fabricate TLS hashes from User-Agent or HTTP headers.
     - Trusted boundary: If deployed behind an authentic upstream TLS terminator, read trusted forwarding headers ONLY if the remote socket IP matches configured trusted proxy IPs; strip all forged client-supplied TLS headers from untrusted clients.
  3. **Offline ASN Resolver (`sb.edge.asn`)**:
     - Configurable offline ASN lookup using local IP database or static CIDR table.
     - If database is unconfigured or IP is private/loopback, record `asn: None` with `asn_status: "unavailable"` or `"loopback"`. Never guess or synthesize ASNs.
  4. **Session State & Asset Ratio**:
     - Update in-memory session tracking with durable session 7-tuple: `(session_id, client_ip, asn, ja3_hash, asset_ratio, first_seen, last_seen)`.
     - Track `static_count` and `api_count`; compute `asset_ratio = static_count / max(1, api_count)`.
  5. **Asynchronous Background Telemetry Tap**:
     - Inbound traffic events and session snapshot updates are queued in an asynchronous, non-blocking queue (`asyncio.Queue`).
     - Background worker drains the queue in batches and commits them to the W3 persistence layer.
     - Reverse proxy request path NEVER awaits database disk writes or hash chain computations.
     - Provide clean `drain()` and `flush()` mechanisms for graceful shutdown.
- **Public Programmatic Signatures**:
  ```python
  class RequestContext:
      request: Request
      ip: str
      asn: int | None
      asn_status: str  # "ok" | "unavailable" | "loopback"
      user_agent: str
      ja3_hash: str | None
      ja4_hash: str | None
      tls_version: str | None
      tls_source: str  # "none" | "local_tls" | "trusted_proxy"
      http_version: str  # "HTTP/1.1" | "HTTP/2"
      header_order: list[str]
      header_fp: str
      is_static: bool
      is_api: bool
      is_document: bool
      client_key: str

  def build_context(request: Request) -> RequestContext: ...
  async def handle(request: Request) -> Response: ...
  async def proxy(ctx: RequestContext) -> httpx.Response: ...

  class TelemetryTap:
      @classmethod
      def enqueue_request(
          cls, ctx: RequestContext, session: Session, response_status: int, canary_ids: tuple[str, ...] = ()
      ) -> None: ...  # Freezes immutable payload immediately; no mutable references
      @classmethod
      async def flush(cls) -> None: ...
      @classmethod
      async def drain(cls) -> None: ...
  ```
- **Configuration Variables Introduced**:
  - `SB_ASN_DB_PATH`: Path to offline ASN database (string, default `""`).
  - `SB_TRUSTED_PROXY_IPS`: Comma-separated list of trusted proxy CIDRs/IPs (default `""`).
  - `SB_TELEMETRY_BATCH_SIZE`: Telemetry queue flush batch size (int, default `50`).
  - `SB_TELEMETRY_FLUSH_INTERVAL_MS`: Telemetry flush interval in milliseconds (int, default `100`).

---

### Task Card W2: Offense Subsystem — Canonical Canary Bindings & Stamping
- **Stream**: Worker 2 (`@w2` / `@hardik`)
- **Owned Modules**:
  - `backend/sb/offense/injector.py`
  - `backend/sb/offense/decoys.py`
  - `backend/sb/offense/honeypots.py`
  - `backend/sb/offense/layer3.py`
  - `backend/sb/offense/matcher.py`
  - `backend/sb/canary/registry.py`
  - `backend/sb/canary/hashing.py`
  - `backend/sb/canary/_defs.py`
  - `backend/sb/hooks.py`
- **Scope & Deliverables**:
  1. **Canonical Canary Token Standard**:
     - All runtime generated canaries strictly conform to format: `SB-CANARY-<session_hash>-<seq>`
     - `session_hash = hashlib.sha256(session_id.encode()).hexdigest()[:32]`, sequence decimal >=4 digits growing without cap.
     - Example: `SB-CANARY-0123456789abcdef0123456789abcdef-0001` (no artificial 8-hex constraint).
     - Bound cryptographically to `session_id`, `vector` (HTML, JSON, API), sequence number, and timestamp.
  2. **Atomic Canary Sequence Counter & Binding**:
     - Utilize W3 store helpers to reserve monotonically increasing per-session sequence counters (`reserve_canary_sequence(session_id, conn=None)`).
     - Store durable bindings in `session_canary_bindings` table; emit chained `canary_binding` event to ledger.
     - Provide `extract_canary_ids(body: bytes) -> tuple[str, ...]` for W1 capture and agreed `SessionCanaryBinding`.
  3. **Additive Response Mutation Engine**:
     - Continue unconditional SANDBOX mutation for eligible upstream HTML and JSON bodies.
     - Inject stamped canary tokens, decoy links, and honey-keys; non-eligible responses pass uncorrupted.
     - Deterministic fallback on parsing failures without leaking internal exceptions.
  4. **Decoy & Honey-Route Handling**:
     - Intercept configured trap paths (`SB_TRAP_PATHS`, `SB_TRAP_API_PATH`) and serve deceptive payloads.
- **Public Programmatic Signatures**:
  ```python
  def bind_session_canary(
      session_id: str,
      vector: str = "HTML",
      value: str | None = None,
      ts: str | None = None,
      conn: sqlite3.Connection | None = None,
  ) -> SessionCanaryBinding: ...

  def reserve_canary_sequence(
      session_id: str,
      conn: sqlite3.Connection | None = None,
  ) -> int: ...

  def extract_canary_ids(body: bytes) -> tuple[str, ...]: ...

  def transform_response(
      ctx: RequestContext,
      session: Session,
      upstream: UpstreamResponse,
  ) -> bytes: ...

  def handle_decoy(
      ctx: RequestContext,
      session: Session,
  ) -> Response | None: ...
  ```

---

### Task Card W3: Provenance Subsystem — Batch Ledger & Transactional Persistence
- **Stream**: Worker 3 (`@w3` / `@hardik`)
- **Owned Modules**:
  - `backend/sb/store/schema.sql` (sole owner)
  - `backend/sb/store/db.py`
  - `backend/sb/store/ledger.py`
  - `backend/sb/store/sessions.py`
  - `backend/sb/store/traffic.py` (new)
  - `backend/sb/store/canaries.py`
  - `backend/sb/store/models.py` (new)
  - `backend/sb/provenance/`
- **Scope & Deliverables**:
  1. **Database Schema DDL & Migrations (`schema.sql`)**:
     - Update `sessions` table: `(session_id, client_ip, asn, ja3_hash, asset_ratio, first_seen, last_seen)` with `asn INTEGER`.
     - Update `traffic_events` table: `client_ip`, `asn INTEGER`, `ja3_hash`, `ja4_hash`, `http_version`, `header_order`, `tls_source`, `canary_ids`.
     - Preserve append-only triggers on `forensic_ledger` preventing `UPDATE` and `DELETE`.
  2. **Batch Forensic Ledger Appending (`sb.store.ledger`)**:
     - Provide `append_events_batch(events: list[tuple[str, dict]], conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]`.
     - Atomically compute sequential hashes and insert envelopes inside single `BEGIN IMMEDIATE` transaction under `_ledger_lock`.
     - Invariant: Missing `forensic_ledger` table raises `sqlite3.OperationalError` (TAMPERED). Never drop history or re-initialize genesis.
  3. **Transactional Projection + Hash Chain Coupling**:
     - Provide atomic helper `persist_telemetry_batch(events: list[dict], session_updates: list[dict]) -> None`.
     - Single transaction updates mutable projections (`traffic_events`, `sessions`) AND appends immutable forensic records; pair list order preserved.
  4. **Database Reset Policy (`reset_db`)**:
     - `reset_db()` purges mutable operational projections (`traffic_events`, `cases`) but strictly preserves ALL `app_state` initialization marker, `forensic_ledger`, canary counters (`session_canary_sequences`), and durable bindings (`session_canary_bindings`). Never purge `app_state` blindly.
- **Public Programmatic Signatures**:
  ```python
  def append_event(kind: str, record: dict, conn: sqlite3.Connection | None = None) -> dict[str, Any]: ...
  def append_events_batch(events: list[tuple[str, dict]], conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]: ...
  def verify_chain() -> dict[str, Any]:
      # Returns {"result": "VALID" | "TAMPERED", "count": int, "head": str, "errors": list[str]}
      ...
  def save_session_snapshot(session: Session, conn: sqlite3.Connection | None = None) -> None: ...
  def persist_telemetry_batch(events: list[dict[str, Any]], session_updates: list[dict[str, Any]]) -> None: ...
  ```

---

### Task Card W4: Dashboard, API & Contracts — Read Models & Real Live Feed
- **Stream**: Worker 4 (`@w4` / `@harsh` / `@arnav`)
- **Owned Modules**:
  - `backend/sb/api/health.py`
  - `backend/sb/api/sessions.py`
  - `backend/sb/api/traffic.py`
  - `backend/sb/api/overview.py`
  - `backend/sb/contracts.py`
  - `contracts/schemas/`
  - `contracts/fixtures/`
  - `dashboard/` (React 19 / Vite 8.3.1)
- **Scope & Deliverables**:
  1. **Contract Definitions & JSON Schemas**:
     - Update Pydantic models in `backend/sb/contracts.py` and JSON schemas in `contracts/schemas/`:
       - `SessionDetail`: Add `client_ip`, `asn`, `asn_status`, `ja3_hash`, `ja4_hash`, `tls_source`, `asset_ratio`, `static_count`, `api_count`.
       - `TrafficEvent`: Add `client_ip`, `asn`, `ja3_hash`, `ja4_hash`, `http_version`, `header_order`, `tls_source`.
       - `Overview`: Reflect aggregate session counts, traffic volume, asset ratio distributions, and forensic ledger validation status.
       - `Health`: Report status of database, ledger chain, background telemetry queue, and upstream origin.
     - Update test fixtures in `contracts/fixtures/` to match agreed models.
  2. **High-Throughput API Read Models**:
     - Optimize `/api/v1/sessions` and `/api/v1/sessions/{session_id}` queries against indexed SQLite projections.
     - Implement `/api/v1/traffic` with cursor-based pagination (`since_seq`) for real-time streaming updates.
     - Implement `/api/v1/overview` aggregating live metrics from projections.
  3. **Authentic Live Dashboard (React 19)**:
     - Real-time traffic stream visualizer rendering authentic incoming requests with IP, ASN, JA3, and HTTP/2 indicators.
     - Session drawer with asset ratio visualizer (`static_count` vs `api_count`).
     - Forensic ledger viewer displaying cryptographic hash chain blocks, sequence numbers, and verification status.
     - Zero mock data in production builds; UI interfaces strictly with `/api/v1/` endpoints.
- **Contract Schema Models**:
  ```python
  class SessionDetail(BaseModel):
      session_id: str
      client_ip: str
      asn: int | None
      asn_status: str
      ja3_hash: str | None
      ja4_hash: str | None
      tls_source: str
      static_count: int
      api_count: int
      asset_ratio: float
      request_count: int
      state: str
      classification: str
      decision: Literal["FAST_PATH", "SANDBOX"]
      risk_score: int
      first_seen: str
      last_seen: str
      reasons: list[str]
      pages: list[str]
      traps_triggered: list[str]
      canaries_exposed: list[str]
      event_ids: list[str]

  class TrafficEvent(BaseModel):
      seq: int
      event_id: str  # >=128-bit unique identifier
      ts: str
      session_id: str
      client_key: str
      client_ip: str
      asn: int | None
      asn_status: str = "unavailable"
      ja3_hash: str | None
      ja4_hash: str | None
      http_version: str
      header_order: list[str]
      header_fp: str
      tls_source: str
      method: str
      path: str
      status_code: int
      user_agent: str
      decision: Literal["FAST_PATH", "SANDBOX"]
      risk_score: int
      reasons: list[str]
      canary_ids: list[str] = []
  ```

---

### Task Card W5: Packaging, QA, Benchmark, Environment, Governance & Integration
- **Stream**: Worker 5 (`@w5` / Integration Lead)
- **Owned Modules**:
  - `backend/tests/contract/`
  - `backend/tests/integration/`
  - `backend/tests/unit/`
  - `scripts/benchmark_tap.py` (new)
  - `scripts/check_contracts.py`
  - `scripts/check_dashboard.py`
  - `scripts/check_ownership.py`
  - `scripts/grep_gate.py`
  - `scripts/verify_live_boot.py`
  - `docs/phase-reports/` (`PHASE-1-KICKOFF.md`, `PHASE-1.md`)
  - `.github/CODEOWNERS`
  - `Makefile`
  - `.env.example`
  - `README.md`
- **Scope & Deliverables**:
  1. **Phase 1 Kickoff & Interface Publication**:
     - Author and publish `docs/phase-reports/PHASE-1-KICKOFF.md` before any implementation code begins.
  2. **Phase 1 Contract Test Suite**:
     - Author `backend/tests/contract/test_phase1_contracts.py` covering all new public interfaces (W1 context & TLS, W2 canary binding, W3 batch ledger, W4 read models).
  3. **Telemetry Tap Latency Benchmark Harness (`scripts/benchmark_tap.py`)**:
     - Author high-frequency loopback benchmark to evaluate tap added latency at 500 req/s.
     - Measure tap processing time (p95 < 5ms) separately from origin proxy RTT.
     - Validate that queue flush/drain leaves zero lost events and ledger verifies VALID post-burst.
  4. **Quality Gates & Governance**:
     - Update `Makefile` with clean check targets (`check`, `test`, `benchmark-tap`).
     - Update `.env.example` with newly introduced configuration variables.
     - Enforce `scripts/grep_gate.py` guaranteeing zero forbidden tokens across the full tree.
  5. **Final Consolidated Integration & Acceptance**:
     - Merge worker branches sequentially into `phase1-integration`.
     - Execute single bounded verification batch on frozen code.
     - Produce comprehensive `docs/phase-reports/PHASE-1.md` for independent `@verifier` sign-off.

---

## 4. Cryptographic Standards, TLS Truth & Protocol Fidelity

### 4.1 TLS Truth & Boundary
1. **No JA3/JA4 Fabrication**:
   - TLS fingerprints (JA3/JA4) cannot be synthesized from HTTP header order, User-Agent strings, or heuristic guesswork.
   - For plaintext HTTP requests (e.g. standard local test harnesses), `ja3_hash` and `ja4_hash` MUST be stored as `NULL` (`None` in Python), with `tls_source: "none"`.
2. **Local TLS Capture Adapter**:
   - A dedicated local TLS termination adapter will be provided for regression testing that captures real ClientHello handshake bytes and computes valid JA3/JA4 digests.
3. **Trusted Boundary & Anti-Spoofing**:
   - In production or behind reverse proxies, client-supplied headers claiming TLS fingerprints (e.g. `X-Client-JA3`) must be stripped at the edge boundary.
   - Forwarded TLS metadata is accepted only when received from socket IPs explicitly matching `SB_TRUSTED_PROXY_IPS`.

### 4.2 HTTP/2 Protocol Truth
- HTTP/2 pseudo-headers (`:method`, `:path`, `:scheme`, `:authority`) and frame-level header order are captured only when the client establishes an actual HTTP/2 connection.
- HTTP/1.1 connections must faithfully report `http_version: "HTTP/1.1"` and standard HTTP/1 header order. HTTP/2 characteristics must never be simulated or claimed on HTTP/1 connections.

### 4.3 Autonomous System Number (ASN) Truth
- ASN lookup operates strictly offline against a local database or static lookup table via `SB_ASN_DB_PATH`. ASN is typed as `int | None` (SQLite `INTEGER`).
- When an IP is not found in the database, or is a private/loopback address (`127.0.0.1`, `::1`, `10.0.0.0/8`, `192.168.0.0/16`), the system stores `asn: None` with `asn_status: "unavailable"` or `"loopback"`. Synthetic or randomly assigned ASNs are strictly prohibited.

### 4.4 Graceful Degradation (PRD §14)
- In the event that TLS capture or ASN lookup fails or encounters internal errors, the proxy gracefully falls back to `tls_source: "none"` and `asn_status: "unavailable"`.
- Edge request handling and origin proxying never stall or fail due to passive telemetry lookup exceptions.
- `Health` endpoint explicitly surfaces telemetry component status (`ok`, `degraded`, or `unavailable`).
- Zero AWS infrastructure is used or needed for Phase 1.

---

## 5. Latency Truth & Benchmark Methodology

### 5.1 Reconciling Latency Specifications
There is an apparent distinction between PRD v3.0 performance goals and the Eight-Phase Master Plan:
- **Master Phase 1 Goal**: Telemetry tap added latency p95 < 5ms at 500 rps.
- **PRD Fast-Path Target**: Fast-path total proxy latency < 5ms.

**Authoritative Resolution for Phase 1**:
1. Fast-path routing and adaptive EMA score evaluation are **introduced in Phase 2**.
2. In Phase 1, **all origin requests remain in SANDBOX mode** and undergo unconditional eligible HTML/JSON mutation.
3. We choose to measure and enforce the **REAL Phase 1 Telemetry Tap Added Latency**:
   - $\text{Tap Added Latency} = T_{\text{context\_extraction}} + T_{\text{asn\_lookup}} + T_{\text{tls\_extraction}} + T_{\text{queue\_enqueue}}$.
   - **Target**: p95 added latency < 5.0ms under a burst load of 500 requests per second.
4. Full end-to-end sandbox reverse proxy latency (including upstream origin response time, in-memory buffering, and HTML/JSON canary mutation) will be measured and reported separately.
5. **No Fake Fast-Path**: We will NOT introduce a fake fast-path flag or bypass origin mutation in Phase 1 simply to artificially meet the PRD fast-path budget. All observed timings will be reported truthfully.

### 5.2 Benchmark Execution Plan
- Benchmark harness (`scripts/benchmark_tap.py`) launches an ephemeral loopback upstream server and ScrapeBuster edge instance.
- Simulates 500 requests per second of mixed browser HTML and API JSON traffic over a bounded test window.
- Captures per-request tap execution duration, queue ingestion rate, memory footprint, and CPU load.
- Validates queue drain upon shutdown with zero lost events.
- Performs full cryptographic verification (`verify_chain()`) on the resulting `forensic_ledger` to confirm chain validity across all generated events.

---

## 6. Database Schema & Data Models (Phase 1)

The complete SQLite DDL schema for Phase 1 (`backend/sb/store/schema.sql`):

```sql
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
    client_ip TEXT NOT NULL,
    asn INTEGER,
    asn_status TEXT DEFAULT 'unavailable',
    ja3_hash TEXT,
    ja4_hash TEXT,
    tls_source TEXT DEFAULT 'none',
    http_version TEXT DEFAULT 'HTTP/1.1',
    header_order TEXT NOT NULL, -- JSON array of raw header names
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
    canary_ids TEXT DEFAULT '[]' -- JSON array of served canary IDs
);

-- Mutable Operational Projections: Sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    client_key TEXT NOT NULL,
    client_ip TEXT NOT NULL,
    asn INTEGER,
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
```

---

## 7. Exit Criteria and Evidence Plan (Phase 1)

| Exit Criterion | Target Description | Validation Method / Expected Evidence |
|---|---|---|
| **EC-01** | Agent Model Dispatch Verification | Record dispatch provider and model in metadata and report (Antigravity Gemini, model/version UNKNOWN (null); never claim Flash 3.8). |
| **EC-02** | Authoritative PRD v3.0 Compliance | Verify FR1.1–FR1.5 and Milestone 1 features without forbidden tokens or perimeter shims. |
| **EC-03** | Worktree Isolation & Merge Sequence | Verified isolated branches off accepted main (`3611b0eb`); sequential merge into `phase1-integration`. |
| **EC-04** | Disjoint Codebase Ownership | `python scripts/check_ownership.py` passes with zero cross-stream violations. |
| **EC-05** | Real TLS & Protocol Truth | Regression tests with genuine ClientHello capture; plaintext traffic has `ja3_hash=None`; raw H2 header order; spoof headers stripped; offline ASN. |
| **EC-06** | Durable Session State & Asset Ratio | Session 7-tuple verified in SQLite and ledger; rolling `asset_ratio` computed correctly on mixed browser/API traffic. |
| **EC-07** | Single SHA-256 Hash Chain Integrity | All forensic events linked in `forensic_ledger`; `verify_chain()` returns `VALID`; `reset_db()` preserves chain and bindings. |
| **EC-08** | Whole-Tree Byte Grep Cleanliness | `python scripts/grep_gate.py .` passes with 0 violations outside `.git`. |
| **EC-09** | Contract & Schema Compliance | `python scripts/check_contracts.py` passes all JSON schemas and updated fixtures; Pydantic models align. |
| **EC-10** | Test Suite & Quality Gate | `make check` exits 0: all unit, contract, and integration tests pass; dashboard typecheck passes. |
| **EC-11** | Tap Latency Benchmark & Live Boot | `python scripts/benchmark_tap.py` confirms tap added latency p95 < 5ms at 500 req/s; live boot passes with valid chain. |
| **EC-12** | Cloud Infrastructure Policy | `N/A no AWS this phase`; zero cloud resources accessed, modified, or provisioned. |

---

## 8. Worker 5 Contract Tests Plan (Same-Phase Verification)

Worker 5 will author and execute the following same-phase contract tests in `backend/tests/contract/test_phase1_contracts.py`:

1. `test_contract_w1_request_context_fields`:
   - Validates that `RequestContext` instantiates all required Phase 1 fields (`client_ip`, `asn`, `asn_status`, `ja3_hash`, `ja4_hash`, `tls_source`, `http_version`, `header_order`, `header_fp`, `is_static`, `is_api`).
   - Verifies that plaintext requests produce `ja3_hash=None`, `ja4_hash=None`, and `tls_source="none"`.
2. `test_contract_w1_tls_capture_and_spoof_stripping`:
   - Tests genuine ClientHello extraction against the local TLS termination adapter.
   - Tests that untrusted client headers attempting to inject `X-Client-JA3` are stripped at the edge.
3. `test_contract_w1_background_telemetry_queue`:
   - Enqueues 1,000 requests into the telemetry queue; verifies non-blocking request loop.
   - Calls `flush()` and `drain()`; asserts zero dropped events in the database and ledger.
4. `test_contract_w2_canary_format_and_sequence`:
   - Validates that generated canaries strictly match `^SB-CANARY-[a-f0-9]{32}-\d{4,}$`.
   - Tests per-session monotonic sequence incrementation across concurrent bindings.
5. `test_contract_w3_batch_ledger_atomicity`:
   - Tests `append_events_batch` with 100 mixed events.
   - Asserts that all events appear contiguously in `forensic_ledger` with unbroken SHA-256 hashes.
   - Asserts that transaction rollback on invalid data leaves the hash chain intact.
6. `test_contract_w3_reset_db_preservation`:
   - Appends events, bindings, and session records, then calls `reset_db()`.
   - Asserts that `forensic_ledger`, `session_canary_bindings`, and `session_canary_sequences` remain intact while operational tables are reset.
7. `test_contract_w4_api_read_models`:
   - Queries `/api/v1/sessions`, `/api/v1/sessions/{id}`, `/api/v1/traffic`, `/api/v1/overview`, `/api/v1/health`.
   - Validates returned payloads strictly against `contracts/schemas/` JSON schemas.
8. `test_contract_w5_tap_latency_burst`:
   - Executes 500 req/s load test via `scripts/benchmark_tap.py`.
   - Asserts tap added latency p95 < 5.0ms.

---

## 9. Midpoint Protocol & Anti-Idle Backlog

### 9.1 Midpoint 5-Line Status Protocol
During Phase 1 execution, workers must emit a 5-line checkpoint status via `orca orchestration send` at every major milestone:
```
LINE 1: Worker & Branch: W<X> on phase1/w<X>-<slug>
LINE 2: Current Task & Target Module: <module/feature being implemented>
LINE 3: Completed Units & Passing Assertions: <count of unit/contract tests or features completed>
LINE 4: Active Challenge / Subsystem Interface: <current integration touchpoint or dependency>
LINE 5: Next Immediate Checkpoint: <next file to author/verify>
```

### 9.2 Anti-Idle Backlog
If a worker completes its primary deliverables or is waiting for an upstream merge into `phase1-integration`:
- **W1**: Enhance TLS adapter ciphersuite test matrix; benchmark header ordering hashing performance.
- **W2**: Add test cases for complex JSON nested structures in canary payload stamping.
- **W3**: Stress test SQLite WAL concurrency with multi-threaded `append_events_batch` writers.
- **W4**: Refine dashboard latency graph components and improve traffic table filtering.
- **W5**: Pre-generate fixture datasets for Phase 2 benchmark scenarios; maintain documentation and audit manifests.
