# ScrapeBuster v3 Pure Layer 3 Full Offense — Phase 0 Architecture Kickoff

- **Document Status**: IN PROGRESS / NOT ACCEPTED (Authoritative planning record; implementation edits strictly prohibited; test execution NOT RUN)
- **Phase**: Phase 0 (Planning & Architecture Kickoff)
- **Workstream Owner**: Worker 5 (W5 Kickoff, Documentation, Governance & Integration)
- **Worker Branch**: `phase0/w5-kickoff`
- **Baseline Git Commit**: `36875140b32af4a32771696e3a2c2f06cd99e201` (Clean working tree independently observed)
- **Agent Model Confirmation**: Gemini (Gemini 3.8 Flash) confirmed effective dispatch model
- **Authoritative Specification**: User-supplied `ScrapeBuster_L3_Full_Offense_PRD.md` v3.0 (Approved 2026-10-07; conversation supplied). Supersedes all legacy v2 and hackathon plans.
- **Literal PRD Policy**: Literal PRD text is intentionally omitted from committed repository files to maintain zero forbidden tokens outside `.git`. Requirements are cited strictly by PRD version and formal section identifiers.

---

## 1. Architectural Vision: Pure Layer 3 Full Offense

ScrapeBuster v3 transitions from a hybrid defensive filtering and challenge posture to a pure offensive instrumentation platform ("Pure Layer 3 Full Offense").

### 1.1 Guiding Principles
1. **Total Elimination of Blocking and Challenge**:
   - All legacy client rate-limiting, IP/fingerprint blocking, and interactive verification (formerly client challenge scripts and proof-of-work mechanics) are decommissioned and removed from the active request path.
   - Every inbound client request is permitted to reach upstream resources and receives a valid application response.
2. **Unconditional Offensive Mutation**:
   - Rather than dropping or interrogating malicious clients, the proxy transparently serves requested resources while injecting subtle, trackable offensive markers (canary seeds, decoy paths, watermarked payloads).
   - In Phase 0, a sandbox policy applies to all eligible HTML and JSON response bodies from the upstream origin (health and control diagnostic routes bypass mutation). Selective heuristics or traffic classification are deferred to Phase 2.
3. **Transparent Upstream Proxying**:
   - Responses are fetched from the authoritative upstream origin defined by `SB_UPSTREAM_ORIGIN`.
   - Non-eligible response bodies (e.g. streaming binary media, HTTP 204 No Content, HTTP HEAD responses) remain completely uncorrupted.
4. **Deterministic Resilience**:
   - Upstream network faults result in best-effort unmutated pass-through accompanied by loud logging to stderr and the telemetry store.
   - Transformation or canary injection failures trigger a deterministic offensive fallback, ensuring offensive tracking continuity without leaking internal configuration secrets.
5. **Session Identity & Privacy**:
   - Client session identity is derived as an opaque server-side fingerprint.
   - Signed internal state cookies (such as legacy clearance tokens) are strictly prohibited.

---

## 2. Five Workstream Task Cards

### Task Card W1: Edge / Config / Main / Session — Blocking & Interactive Verification Removal
- **Stream**: Worker 1 (W1)
- **Owned Modules**: `backend/sb/edge/`, `backend/sb/config.py`, `backend/sb/main.py`, `backend/sb/edge/session.py`
- **Scope & Deliverables**:
  - Edge pipeline overhaul: Decommission legacy filtering pipelines, rate-limiting windows, and interactive verification endpoints.
  - Implement streamlined asynchronous request flow:
    - `build_context(request: Request) -> RequestContext`
    - `async handle(request: Request) -> Response`
    - `async proxy(ctx: RequestContext) -> Response`
  - Unconditional response mutation: Integrate `sb.offense.injector.transform_response(ctx, session, upstream)` into the proxy response loop.
  - Runtime configuration:
    - Enforce required `SB_UPSTREAM_ORIGIN` (reject empty or legacy branded fallback).
    - Enforce required `SB_PUBLIC_BASE_URL` (per PRD PR-2 dual-origin requirement).
    - Expose `SB_TRAP_PATHS` (JSON list, default `[]`) and `SB_TRAP_API_PATH` (string, default `""`).
    - Preserve `SB_DB_PATH` and `SB_RUNTIME_DIR`.
  - Session management: Transition session state tracking to server-side opaque fingerprints without signed internal clearance cookies.
  - Fault handling: Ensure proxy network faults pass through unmutated with loud logging, while mutation errors fall back to deterministic offensive content.

### Task Card W2: Offense Subsystem — Trap Rename, Generic Seeds & Dynamic Paths
- **Stream**: Worker 2 (W2)
- **Owned Modules**: `backend/sb/offense/` (renamed from `backend/sb/trap/`), `backend/sb/canary/`, `backend/sb/hooks.py`
- **Scope & Deliverables**:
  - Subsystem rename: Refactor `backend/sb/trap/` to `backend/sb/offense/`.
  - Public contract interfaces:
    - Expose `sb.offense.injector.transform_response(ctx, session, upstream) -> bytes`
    - Expose `sb.offense.injector.handle_decoy(ctx, session) -> Response | None`
  - Canary seed genericization: Update canary definitions in `backend/sb/canary/` to generic offensive formats conforming to `SB-CANARY-<session_hash>-<seq>`. Eliminate legacy branded anchors.
  - Configurable decoys: Dynamically generate decoy resources and honey-routes driven by `SB_TRAP_PATHS` and `SB_TRAP_API_PATH`.
  - Hook rewiring: Adapt lifecycle callbacks in `backend/sb/hooks.py` to target the offensive transformation engine.

### Task Card W3: Provenance Subsystem — Event Source Rewiring, Hash Chain & Visible Failures
- **Stream**: Worker 3 (W3)
- **Owned Modules**: `backend/sb/provenance/`, `backend/sb/store/`
- **Scope & Deliverables**:
  - Ingestion rewiring: Rewire provenance exposure event consumers to ingest directly from the offensive mutation pipeline and session event stream.
  - Cryptographic audit chain: Implement single SHA-256 hash chain per PRD FR-7.1 for exposure manifests and case evidence (resolving legacy descriptive Merkle wording).
  - Visible failure states: Replace silent fallbacks with explicit, observable failure outcomes across retrieval, LLM analysis, and correlation. Ensure retrieval misses or timeouts raise structured errors recorded in telemetry.
  - Persistence alignment: Update database models in `backend/sb/store/` (`schema.sql`, `db.py`, `sessions.py`) to record pure offensive session metrics, removing obsolete challenge resolution and block event columns.

### Task Card W4: Dashboard & Contracts — Interface Purge & Telemetry Feeds
- **Stream**: Worker 4 (W4)
- **Owned Modules**: `dashboard/`, `backend/sb/api/`, `backend/sb/contracts.py`, `contracts/schemas/`, `contracts/fixtures/`
- **Scope & Deliverables**:
  - Dashboard component purge: Remove all legacy interactive challenge controls, proof-of-work status badges, and blocking visualizers from React views (`Overview.tsx`, `Traffic.tsx`, `SessionDrawer.tsx`, etc.).
  - Offensive UI feeds: Update real-time views to present incoming session volume, offensive injection metrics, canary token distribution, and provenance correlation results.
  - Contract schemas: Update JSON Schemas (`contracts/schemas/`) and test fixtures (`contracts/fixtures/`) to reflect pure Layer 3 contracts (`Health`, `TrafficEvents`, `SessionDetail`, `Overview`).
  - Cross-stream coordination: Announce any schema or public API adjustments via orchestration prior to branch merge.

### Task Card W5: Repository Governance — Cleanup, Test Relocation, Grep Gate & Final Verification
- **Stream**: Worker 5 (W5)
- **Owned Modules**: Repository root, `Makefile`, `scripts/`, test suites, documentation, legacy artifact deletion
- **Scope & Deliverables**:
  - Legacy subsystem deletion: Remove 125 obsolete files identified in the deletion inventory upon user authorization, coordinating `backend/sb/demo/` removal with W1 and W4.
  - Grep gate enforcement: Author and execute `scripts/grep_gate.sh`, guaranteeing zero forbidden tokens outside `.git`, case-insensitive.
  - Test suite relocation: Adapt and relocate surviving unit and integration tests to validate pure offensive contracts.
  - Build automation: Update `Makefile` with clean targets (`check`, `test`, `grep-gate`, `clean`).
  - Integrated verification: Execute complete `make check` suite on `phase0-integration` and compile final verification report for independent verifier sign-off.

---

## 3. Proposed & Approved System Contracts (PRD v3.0)

### 3.1 Request Handling Lifecycle
```
[Inbound Client Request]
       │
       ▼
1. build_context(request) ──> RequestContext (headers, path, IP, fingerprint)
       │
       ▼
2. session resolution     ──> Session (opaque server-side identity)
       │
       ▼
3. telemetry ingestion    ──> Inbound event recorded
       │
       ▼
4. proxy(ctx)             ──> Forward to SB_UPSTREAM_ORIGIN ──> UpstreamResponse
       │
       ▼
5. transform_response()   ──> Unconditional Offensive Mutation (HTML/JSON)
       │
       ▼
6. response emission      ──> Emitted to Client with injected tokens
```

### 3.2 Programmatic Signatures
- `build_context(request: Request) -> RequestContext`
- `async handle(request: Request) -> Response`
- `async proxy(ctx: RequestContext) -> UpstreamResponse`
- `sb.offense.injector.transform_response(ctx: RequestContext, session: Session, upstream: UpstreamResponse) -> bytes`
- `sb.offense.injector.handle_decoy(ctx: RequestContext, session: Session) -> Response | None`

### 3.3 Token & Cryptographic Standards
- **Canary Format**: `SB-CANARY-<session_hash>-<seq>`
- **Hash Chain**: Single SHA-256 linear hash chain across published canaries and exposure records (PRD FR-7.1).

### 3.4 Runtime Configuration Matrix
| Variable | Type | Required | Default | Description |
|---|---|---|---|---|
| `SB_UPSTREAM_ORIGIN` | URL String | YES | (None; strictly required) | Target origin URL; no branded fallback permitted. |
| `SB_PUBLIC_BASE_URL` | URL String | YES | (None; strictly required) | External base URL for decoy linking and telemetry resolution (PRD PR-2). |
| `SB_TRAP_PATHS` | JSON Array | NO | `[]` | Comma-separated or JSON list of runtime offensive decoy paths. |
| `SB_TRAP_API_PATH` | String | NO | `""` | Dedicated path prefix for offensive decoy API responses. |
| `SB_DB_PATH` | Path | NO | `sb.db` | Local SQLite database location (preserved). |
| `SB_RUNTIME_DIR` | Path | NO | `runtime/` | Local runtime state directory (preserved). |

### 3.5 Operational Invariants
- **No Binary / Stream Corruption**: Non-HTML/JSON response bodies (images, streaming video, downloads, HEAD requests, HTTP 204) pass through unmutated.
- **No Signed Cookies**: No internal clearance cookies; session identification relies on server-side fingerprinting.
- **Deterministic Offense Fallback**: When payload injection encounters internal parsing errors, an offensive fallback payload is served.
- **Proxy Network Fault Resilience**: Connection refused or socket timeouts from upstream trigger best-effort unmutated 502/504 pass-through with loud error logging.
- **Visible Failure Reporting**: Subsystem errors must be explicitly logged and surfaced in API error payloads; no silent masking.

---

## 4. Branching and Integration Policy

```
[phase0/w1-edge]       ──┐
[phase0/w2-offense]    ──┤
[phase0/w3-provenance] ──┼──> [phase0-integration] ──(Independent Verifier Gate)──> [main]
[phase0/w4-dashboard]  ──┤
[phase0/w5-cleanup]    ──┘
```

1. **Worker Isolation**: Each stream operates strictly within its designated worker branch (`phase0/w1-edge` through `phase0/w5-cleanup`).
2. **Intermediate Integration**: Stream branches merge into `phase0-integration` upon completion of stream-specific deliverables.
3. **No Mid-Flight Test Runs**: Sibling workers do not run tests, lint, or formatters mid-flight. W5 executes the single comprehensive test suite on `phase0-integration`.
4. **Independent Verifier Gate**: `main` remains untouched at commit `36875140b32af4a32771696e3a2c2f06cd99e201`. Merging into `main` occurs strictly after independent verifier evaluation of the clean integration branch.

---

## 5. Read-Only Legacy Deletion Inventory (125 Files)

### 5.1 Deterministic Decoding Instructions
To prevent accidental whole-tree grep violations from legacy path names, all 125 files slated for deletion are encoded as sequences of Unicode code points (`U+XXXX`).

**Decoding Algorithms**:
- **Python**:
  ```python
  decoded_path = "".join(chr(int(cp[2:], 16)) for cp in code_points.split())
  ```
- **JavaScript**:
  ```javascript
  const decodedPath = codePoints.split(" ").map(cp => String.fromCharCode(parseInt(cp.slice(2), 16))).join("");
  ```
- **PowerShell**:
  ```powershell
  $decodedPath = -join ($codePoints -split ' ' | ForEach-Object { [char][convert]::ToInt32($_.Substring(2), 16) })
  ```

### 5.2 Deletion Table
| Opaque ID | Subsystem Category | Encoded Legacy Relative Path (Unicode Code Points) |
|---|---|---|
| DEL-001 | Superseded Workflow & Checkpoint | `U+002E U+0067 U+0069 U+0074 U+0068 U+0075 U+0062 U+002F U+006A U+0075 U+006C U+0065 U+0073 U+002D U+0072 U+0065 U+0076 U+0069 U+0065 U+0077 U+002D U+0063 U+006F U+006E U+0066 U+0069 U+0067 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-002 | Superseded Docs & Plans | `U+002E U+0067 U+0069 U+0074 U+0068 U+0075 U+0062 U+002F U+006A U+0075 U+006C U+0065 U+0073 U+002D U+0072 U+0065 U+0076 U+0069 U+0065 U+0077 U+002D U+0072 U+0075 U+006C U+0065 U+0073 U+002E U+006D U+0064` |
| DEL-003 | Superseded Workflow & Checkpoint | `U+002E U+0067 U+0069 U+0074 U+0068 U+0075 U+0062 U+002F U+0073 U+0063 U+0072 U+0069 U+0070 U+0074 U+0073 U+002F U+006A U+0075 U+006C U+0065 U+0073 U+002D U+0070 U+0072 U+002D U+0072 U+0065 U+0076 U+0069 U+0065 U+0077 U+002E U+006D U+006A U+0073` |
| DEL-004 | Superseded Workflow & Checkpoint | `U+002E U+0067 U+0069 U+0074 U+0068 U+0075 U+0062 U+002F U+0077 U+006F U+0072 U+006B U+0066 U+006C U+006F U+0077 U+0073 U+002F U+006A U+0075 U+006C U+0065 U+0073 U+002D U+0070 U+0072 U+002D U+0072 U+0065 U+0076 U+0069 U+0065 U+0077 U+002E U+0079 U+006D U+006C` |
| DEL-005 | Superseded Workflow & Checkpoint | `U+002E U+006F U+006D U+0070 U+002F U+0063 U+0068 U+0065 U+0063 U+006B U+0070 U+006F U+0069 U+006E U+0074 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-006 | Superseded Docs & Plans | `U+002E U+006F U+006D U+0070 U+002F U+0068 U+0061 U+006E U+0064 U+006F U+0066 U+0066 U+002E U+006D U+0064` |
| DEL-007 | Superseded Docs & Plans | `U+0053 U+0043 U+0041 U+0050 U+0045 U+0042 U+0055 U+0053 U+0054 U+0045 U+0052 U+0053 U+005F U+004D U+0041 U+0053 U+0054 U+0045 U+0052 U+005F U+0049 U+004D U+0050 U+004C U+0045 U+004D U+0045 U+004E U+0054 U+0041 U+0054 U+0049 U+004F U+004E U+005F U+0050 U+004C U+0041 U+004E U+002E U+006D U+0064` |
| DEL-008 | Superseded Docs & Plans | `U+005F U+0074 U+006D U+0070 U+005F U+0073 U+0065 U+0063 U+0033 U+002E U+0074 U+0078 U+0074` |
| DEL-009 | Superseded Docs & Plans | `U+005F U+0074 U+006D U+0070 U+005F U+0073 U+0065 U+0063 U+0035 U+002E U+0074 U+0078 U+0074` |
| DEL-010 | Legacy Attack Harness | `U+0061 U+0074 U+0074 U+0061 U+0063 U+006B U+0073 U+002F U+0061 U+0064 U+0076 U+0061 U+006E U+0063 U+0065 U+0064 U+005F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+002E U+0070 U+0079` |
| DEL-011 | Legacy Attack Harness | `U+0061 U+0074 U+0074 U+0061 U+0063 U+006B U+0073 U+002F U+0063 U+006F U+006D U+006D U+006F U+006E U+002E U+0070 U+0079` |
| DEL-012 | Legacy Attack Harness | `U+0061 U+0074 U+0074 U+0061 U+0063 U+006B U+0073 U+002F U+0068 U+0075 U+006D U+0061 U+006E U+005F U+0063 U+006F U+006E U+0074 U+0072 U+006F U+006C U+002E U+0070 U+0079` |
| DEL-013 | Legacy Attack Harness | `U+0061 U+0074 U+0074 U+0061 U+0063 U+006B U+0073 U+002F U+006F U+0072 U+0064 U+0069 U+006E U+0061 U+0072 U+0079 U+005F U+0062 U+006F U+0074 U+002E U+0070 U+0079` |
| DEL-014 | Legacy Attack Harness | `U+0061 U+0074 U+0074 U+0061 U+0063 U+006B U+0073 U+002F U+0073 U+0069 U+0074 U+0065 U+0073 U+002E U+0070 U+0079` |
| DEL-015 | Legacy Attack Harness | `U+0061 U+0074 U+0074 U+0061 U+0063 U+006B U+0073 U+002F U+0073 U+006F U+0070 U+0068 U+0069 U+0073 U+0074 U+0069 U+0063 U+0061 U+0074 U+0065 U+0064 U+005F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+002E U+0070 U+0079` |
| DEL-016 | Legacy Demo Subsystem | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0061 U+0070 U+0069 U+002F U+0064 U+0065 U+006D U+006F U+002E U+0070 U+0079` |
| DEL-017 | Legacy Demo Subsystem | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0064 U+0065 U+006D U+006F U+002F U+005F U+005F U+0069 U+006E U+0069 U+0074 U+005F U+005F U+002E U+0070 U+0079` |
| DEL-018 | Legacy Demo Subsystem | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0064 U+0065 U+006D U+006F U+002F U+0067 U+006F U+006C U+0064 U+0065 U+006E U+002E U+0070 U+0079` |
| DEL-019 | Legacy Demo Subsystem | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0064 U+0065 U+006D U+006F U+002F U+0072 U+0065 U+0073 U+0065 U+0074 U+002E U+0070 U+0079` |
| DEL-020 | Legacy Demo Subsystem | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0064 U+0065 U+006D U+006F U+002F U+0072 U+0075 U+006E U+006E U+0065 U+0072 U+002E U+0070 U+0079` |
| DEL-021 | Legacy Edge Defense | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0065 U+0064 U+0067 U+0065 U+002F U+0069 U+006E U+0074 U+0065 U+006C U+002E U+0070 U+0079` |
| DEL-022 | Legacy Edge Defense | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0065 U+0064 U+0067 U+0065 U+002F U+006C U+0061 U+0079 U+0065 U+0072 U+0031 U+002E U+0070 U+0079` |
| DEL-023 | Legacy Edge Defense | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0065 U+0064 U+0067 U+0065 U+002F U+006C U+0061 U+0079 U+0065 U+0072 U+0032 U+002E U+0070 U+0079` |
| DEL-024 | Legacy Edge Defense | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0073 U+0062 U+002F U+0065 U+0064 U+0067 U+0065 U+002F U+0073 U+0074 U+0061 U+0074 U+0069 U+0063 U+002F U+0063 U+0068 U+0061 U+006C U+006C U+0065 U+006E U+0067 U+0065 U+002E U+006A U+0073` |
| DEL-025 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0065 U+0032 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+0066 U+0075 U+006C U+006C U+005F U+0064 U+0065 U+006D U+006F U+002E U+0070 U+0079` |
| DEL-026 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0065 U+0032 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+006C U+0032 U+005F U+0061 U+0064 U+0076 U+0061 U+006E U+0063 U+0065 U+0064 U+002E U+0070 U+0079` |
| DEL-027 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0065 U+0032 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+006C U+0033 U+005F U+0073 U+006F U+0070 U+0068 U+0069 U+0073 U+0074 U+0069 U+0063 U+0061 U+0074 U+0065 U+0064 U+002E U+0070 U+0079` |
| DEL-028 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0065 U+0032 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+006E U+006F U+0072 U+006D U+0061 U+006C U+005F U+0075 U+0073 U+0065 U+0072 U+002E U+0070 U+0079` |
| DEL-029 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0065 U+0032 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+0072 U+0065 U+0073 U+0065 U+0074 U+002E U+0070 U+0079` |
| DEL-030 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0069 U+006E U+0074 U+0065 U+0067 U+0072 U+0061 U+0074 U+0069 U+006F U+006E U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+006C U+0031 U+005F U+006F U+0072 U+0064 U+0069 U+006E U+0061 U+0072 U+0079 U+005F U+0062 U+006F U+0074 U+002E U+0070 U+0079` |
| DEL-031 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0069 U+006E U+0074 U+0065 U+0067 U+0072 U+0061 U+0074 U+0069 U+006F U+006E U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+006C U+0061 U+0079 U+0065 U+0072 U+0032 U+005F U+0066 U+006C U+006F U+0077 U+002E U+0070 U+0079` |
| DEL-032 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0069 U+006E U+0074 U+0065 U+0067 U+0072 U+0061 U+0074 U+0069 U+006F U+006E U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+0070 U+0068 U+0061 U+0073 U+0065 U+0031 U+005F U+0063 U+0061 U+006D U+0070 U+0075 U+0073 U+0063 U+0061 U+0072 U+0074 U+002E U+0070 U+0079` |
| DEL-033 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0075 U+006E U+0069 U+0074 U+002F U+0064 U+0065 U+006D U+006F U+002F U+005F U+005F U+0069 U+006E U+0069 U+0074 U+005F U+005F U+002E U+0070 U+0079` |
| DEL-034 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0075 U+006E U+0069 U+0074 U+002F U+0064 U+0065 U+006D U+006F U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+0067 U+006F U+006C U+0064 U+0065 U+006E U+002E U+0070 U+0079` |
| DEL-035 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0075 U+006E U+0069 U+0074 U+002F U+0064 U+0065 U+006D U+006F U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+0072 U+0075 U+006E U+006E U+0065 U+0072 U+005F U+0073 U+0061 U+0066 U+0065 U+0074 U+0079 U+002E U+0070 U+0079` |
| DEL-036 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0075 U+006E U+0069 U+0074 U+002F U+0065 U+0064 U+0067 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+0069 U+006E U+0074 U+0065 U+006C U+002E U+0070 U+0079` |
| DEL-037 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0075 U+006E U+0069 U+0074 U+002F U+0065 U+0064 U+0067 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+006C U+0061 U+0079 U+0065 U+0072 U+0031 U+002E U+0070 U+0079` |
| DEL-038 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0075 U+006E U+0069 U+0074 U+002F U+0065 U+0064 U+0067 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+006C U+0061 U+0079 U+0065 U+0072 U+0032 U+002E U+0070 U+0079` |
| DEL-039 | Legacy Test Suite | `U+0062 U+0061 U+0063 U+006B U+0065 U+006E U+0064 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0075 U+006E U+0069 U+0074 U+002F U+0065 U+0064 U+0067 U+0065 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+0070 U+0069 U+0070 U+0065 U+006C U+0069 U+006E U+0065 U+005F U+006C U+0031 U+005F U+0067 U+0061 U+0074 U+0065 U+002E U+0070 U+0079` |
| DEL-040 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0062 U+0061 U+0073 U+0065 U+006C U+0069 U+006E U+0065 U+002F U+0070 U+0075 U+0062 U+006C U+0069 U+0063 U+005F U+0062 U+0061 U+0073 U+0065 U+006C U+0069 U+006E U+0065 U+002E U+006A U+0073 U+006F U+006E U+006C` |
| DEL-041 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0063 U+0061 U+006E U+0061 U+0072 U+0079 U+005F U+006D U+0061 U+006E U+0069 U+0066 U+0065 U+0073 U+0074 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-042 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0063 U+006F U+006E U+0074 U+0072 U+006F U+006C U+002F U+0063 U+006F U+006E U+0074 U+0072 U+006F U+006C U+005F U+0063 U+006C U+0065 U+0061 U+006E U+002E U+006A U+0073 U+006F U+006E U+006C` |
| DEL-043 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0064 U+0061 U+0074 U+0061 U+0073 U+0065 U+0074 U+0073 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0031 U+0034 U+0034 U+0031 U+0034 U+005F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+0033 U+002E U+006A U+0073 U+006F U+006E U+006C` |
| DEL-044 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0064 U+0061 U+0074 U+0061 U+0073 U+0065 U+0074 U+0073 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+005F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+0033 U+002E U+006A U+0073 U+006F U+006E U+006C` |
| DEL-045 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0031 U+0034 U+0034 U+0031 U+0034 U+002F U+0068 U+0075 U+006D U+0061 U+006E U+005F U+0072 U+0065 U+006E U+0064 U+0065 U+0072 U+0065 U+0064 U+005F U+0063 U+0061 U+006D U+0070 U+0075 U+0073 U+0063 U+0061 U+0072 U+0074 U+002E U+0070 U+006E U+0067` |
| DEL-046 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0031 U+0034 U+0034 U+0031 U+0034 U+002F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+0033 U+002E U+006F U+0072 U+0069 U+0067 U+0069 U+006E U+0061 U+006C U+002E U+006A U+0073 U+006F U+006E U+006C` |
| DEL-047 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0061 U+0064 U+0076 U+0061 U+006E U+0063 U+0065 U+0064 U+005F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-048 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0063 U+0061 U+006E U+0061 U+0072 U+0069 U+0065 U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-049 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0063 U+0061 U+0073 U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-050 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0063 U+006F U+006E U+0074 U+0072 U+006F U+006C U+005F U+0070 U+0072 U+006F U+0062 U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-051 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+005F U+0061 U+0070 U+0069 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-052 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0065 U+0078 U+0070 U+006F U+0073 U+0075 U+0072 U+0065 U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-053 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0068 U+0075 U+006D U+0061 U+006E U+005F U+0063 U+006F U+006E U+0074 U+0072 U+006F U+006C U+002E U+006A U+0073 U+006F U+006E` |
| DEL-054 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0068 U+0075 U+006D U+0061 U+006E U+005F U+0072 U+0065 U+006E U+0064 U+0065 U+0072 U+0065 U+0064 U+005F U+0063 U+0061 U+006D U+0070 U+0075 U+0073 U+0063 U+0061 U+0072 U+0074 U+002E U+0070 U+006E U+0067` |
| DEL-055 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+006F U+0072 U+0064 U+0069 U+006E U+0061 U+0072 U+0079 U+005F U+0062 U+006F U+0074 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-056 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0070 U+0075 U+0062 U+006C U+0069 U+0063 U+0061 U+0074 U+0069 U+006F U+006E U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-057 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+0033 U+002E U+006F U+0072 U+0069 U+0067 U+0069 U+006E U+0061 U+006C U+002E U+006A U+0073 U+006F U+006E U+006C` |
| DEL-058 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0073 U+0065 U+0073 U+0073 U+0069 U+006F U+006E U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-059 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0073 U+006F U+0070 U+0068 U+0069 U+0073 U+0074 U+0069 U+0063 U+0061 U+0074 U+0065 U+0064 U+005F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-060 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0074 U+0061 U+0072 U+0067 U+0065 U+0074 U+005F U+0070 U+0072 U+006F U+0062 U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-061 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0074 U+0072 U+0061 U+0066 U+0066 U+0069 U+0063 U+005F U+0065 U+0076 U+0065 U+006E U+0074 U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-062 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0074 U+0072 U+0061 U+0070 U+005F U+0068 U+0069 U+0074 U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-063 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0076 U+0065 U+0072 U+0069 U+0066 U+0069 U+0063 U+0061 U+0074 U+0069 U+006F U+006E U+002E U+006A U+0073 U+006F U+006E` |
| DEL-064 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0031 U+005F U+0063 U+0061 U+006E U+0061 U+0072 U+0079 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-065 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0032 U+005F U+0070 U+0075 U+0062 U+006C U+0069 U+0063 U+0061 U+0074 U+0069 U+006F U+006E U+005F U+0072 U+0065 U+0063 U+006F U+0072 U+0064 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-066 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0033 U+005F U+0065 U+0078 U+0070 U+006F U+0073 U+0075 U+0072 U+0065 U+005F U+0065 U+0076 U+0065 U+006E U+0074 U+0073 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-067 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0034 U+005F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+005F U+0070 U+0072 U+006F U+0066 U+0069 U+006C U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-068 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0035 U+005F U+0070 U+0072 U+006F U+0062 U+0065 U+005F U+0072 U+0065 U+0071 U+0075 U+0065 U+0073 U+0074 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-069 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0036 U+005F U+006D U+006F U+0064 U+0065 U+006C U+005F U+0072 U+0065 U+0073 U+0070 U+006F U+006E U+0073 U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-070 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0037 U+005F U+0063 U+006F U+006E U+0074 U+0072 U+006F U+006C U+005F U+0072 U+0065 U+0073 U+0070 U+006F U+006E U+0073 U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-071 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0038 U+005F U+006D U+0061 U+0074 U+0063 U+0068 U+005F U+0061 U+006E U+0061 U+006C U+0079 U+0073 U+0069 U+0073 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-072 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0039 U+005F U+0066 U+0069 U+006E U+0064 U+0069 U+006E U+0067 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-073 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+006D U+0061 U+006E U+0069 U+0066 U+0065 U+0073 U+0074 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-074 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0063 U+0061 U+0073 U+0065 U+005F U+0061 U+0070 U+0069 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-075 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0063 U+0068 U+0061 U+0069 U+006E U+002E U+006A U+0073 U+006F U+006E` |
| DEL-076 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0064 U+0061 U+0073 U+0068 U+0062 U+006F U+0061 U+0072 U+0064 U+005F U+006C U+0069 U+0076 U+0065 U+002E U+0070 U+006E U+0067` |
| DEL-077 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0064 U+0061 U+0073 U+0068 U+0062 U+006F U+0061 U+0072 U+0064 U+005F U+0072 U+0065 U+0063 U+006F U+0072 U+0064 U+0065 U+0064 U+002E U+0070 U+006E U+0067` |
| DEL-078 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0068 U+0075 U+006D U+0061 U+006E U+005F U+0063 U+0061 U+006D U+0070 U+0075 U+0073 U+0063 U+0061 U+0072 U+0074 U+002E U+0070 U+006E U+0067` |
| DEL-079 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0070 U+0072 U+006F U+0062 U+0065 U+0073 U+005F U+0061 U+0070 U+0069 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-080 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+0033 U+002E U+0072 U+0065 U+0068 U+0065 U+0061 U+0072 U+0073 U+0061 U+006C U+002E U+006A U+0073 U+006F U+006E U+006C` |
| DEL-081 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0073 U+0065 U+0063 U+0075 U+0072 U+0069 U+0074 U+0079 U+005F U+0064 U+0062 U+005F U+0073 U+006E U+0061 U+0070 U+0073 U+0068 U+006F U+0074 U+0073 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-082 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0073 U+0065 U+0073 U+0073 U+0069 U+006F U+006E U+0073 U+005F U+0061 U+0070 U+0069 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-083 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0074 U+0072 U+0061 U+0066 U+0066 U+0069 U+0063 U+005F U+0065 U+0076 U+0065 U+006E U+0074 U+0073 U+005F U+0061 U+0070 U+0069 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-084 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0034 U+0034 U+0034 U+0033 U+0033 U+002F U+0076 U+0065 U+0072 U+0069 U+0066 U+0079 U+005F U+0061 U+0070 U+0069 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-085 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0063 U+0061 U+006E U+0061 U+0072 U+0079 U+005F U+0065 U+0078 U+0070 U+006F U+0073 U+0075 U+0072 U+0065 U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-086 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0068 U+0075 U+006D U+0061 U+006E U+005F U+0072 U+0065 U+006E U+0064 U+0065 U+0072 U+0065 U+0064 U+005F U+0063 U+0061 U+006D U+0070 U+0075 U+0073 U+0063 U+0061 U+0072 U+0074 U+002E U+0070 U+006E U+0067` |
| DEL-087 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0073 U+0065 U+0073 U+0073 U+0069 U+006F U+006E U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-088 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0074 U+0072 U+0061 U+0066 U+0066 U+0069 U+0063 U+005F U+0065 U+0076 U+0065 U+006E U+0074 U+0073 U+005F U+0072 U+0061 U+0077 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-089 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0068 U+0061 U+0063 U+006B U+0061 U+0074 U+0068 U+006F U+006E U+005F U+0076 U+0031 U+005F U+0068 U+0061 U+006E U+0064 U+006F U+0066 U+0066 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-090 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+006D U+0061 U+006E U+0069 U+0066 U+0065 U+0073 U+0074 U+005F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0030 U+0035 U+0031 U+0030 U+0032 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-091 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+006D U+0061 U+006E U+0069 U+0066 U+0065 U+0073 U+0074 U+005F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-092 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0070 U+0068 U+0061 U+0073 U+0065 U+0031 U+0031 U+005F U+0068 U+0061 U+006E U+0064 U+006F U+0066 U+0066 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-093 | Legacy Runs & Datasets | `U+0064 U+0061 U+0074 U+0061 U+002F U+0072 U+0065 U+0070 U+006C U+0061 U+0079 U+002F U+0072 U+0065 U+0070 U+006C U+0061 U+0079 U+005F U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0032 U+0039 U+0054 U+0031 U+0037 U+0031 U+0039 U+0033 U+0034 U+005A U+002E U+006A U+0073 U+006F U+006E` |
| DEL-094 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0041 U+004E U+0049 U+0052 U+0055 U+0044 U+0048 U+005F U+0044 U+0045 U+0046 U+0045 U+0052 U+0052 U+0045 U+0044 U+005F U+0057 U+004F U+0052 U+004B U+002E U+006D U+0064` |
| DEL-095 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0041 U+004E U+0049 U+0052 U+0055 U+0044 U+0048 U+005F U+0049 U+004D U+0050 U+004C U+0045 U+004D U+0045 U+004E U+0054 U+0041 U+0054 U+0049 U+004F U+004E U+005F U+0050 U+004C U+0041 U+004E U+002E U+006D U+0064` |
| DEL-096 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0044 U+0045 U+0043 U+0049 U+0053 U+0049 U+004F U+004E U+0053 U+002E U+006D U+0064` |
| DEL-097 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0048 U+0041 U+0043 U+004B U+0041 U+0054 U+0048 U+004F U+004E U+005F U+0052 U+0045 U+0041 U+0044 U+0049 U+004E U+0045 U+0053 U+0053 U+002E U+006D U+0064` |
| DEL-098 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0048 U+0041 U+0043 U+004B U+0041 U+0054 U+0048 U+004F U+004E U+005F U+0052 U+0055 U+004E U+0042 U+004F U+004F U+004B U+002E U+006D U+0064` |
| DEL-099 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0049 U+004E U+0054 U+0045 U+0047 U+0052 U+0041 U+0054 U+0049 U+004F U+004E U+005F U+004C U+004F U+0047 U+002E U+006D U+0064` |
| DEL-100 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+004A U+0055 U+004C U+0045 U+0053 U+005F U+0052 U+0045 U+0056 U+0049 U+0045 U+0057 U+005F U+0053 U+0057 U+0041 U+0052 U+004D U+002E U+006D U+0064` |
| DEL-101 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0050 U+0048 U+0041 U+0053 U+0045 U+005F U+0030 U+0035 U+005F U+0041 U+004E U+0049 U+005F U+0054 U+0045 U+004C U+0045 U+004D U+0045 U+0054 U+0052 U+0059 U+005F U+0050 U+004C U+0041 U+004E U+002E U+006D U+0064` |
| DEL-102 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0050 U+0048 U+0041 U+0053 U+0045 U+005F U+0030 U+0036 U+005F U+0041 U+004E U+0049 U+005F U+0043 U+004F U+004E U+0054 U+0052 U+0041 U+0043 U+0054 U+005F U+0050 U+004C U+0041 U+004E U+002E U+006D U+0064` |
| DEL-103 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0050 U+0048 U+0041 U+0053 U+0045 U+005F U+0030 U+0037 U+005F U+0048 U+0041 U+0052 U+0044 U+0049 U+004B U+005F U+0043 U+0041 U+004E U+0041 U+0052 U+0049 U+0045 U+0053 U+005F U+0043 U+004F U+004E U+0054 U+0052 U+004F U+004C U+002E U+006D U+0064` |
| DEL-104 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0050 U+0048 U+0041 U+0053 U+0045 U+005F U+0030 U+0039 U+005F U+0041 U+004E U+0049 U+005F U+0044 U+0041 U+0053 U+0048 U+0042 U+004F U+0041 U+0052 U+0044 U+005F U+0050 U+004C U+0041 U+004E U+002E U+006D U+0064` |
| DEL-105 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0050 U+0048 U+0041 U+0053 U+0045 U+005F U+0031 U+0031 U+005F U+0048 U+0041 U+0052 U+0044 U+0049 U+004B U+005F U+0052 U+0045 U+0041 U+004C U+005F U+0050 U+0052 U+004F U+0056 U+0045 U+004E U+0041 U+004E U+0043 U+0045 U+002E U+006D U+0064` |
| DEL-106 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0061 U+0070 U+0069 U+002F U+0049 U+004E U+0054 U+002D U+0030 U+0035 U+002D U+0043 U+006F U+006E U+0074 U+0072 U+006F U+006C U+002D U+0041 U+0050 U+0049 U+002E U+006D U+0064` |
| DEL-107 | Superseded Docs & Plans | `U+0064 U+006F U+0063 U+0073 U+002F U+0061 U+0070 U+0069 U+002F U+0049 U+004E U+0054 U+002D U+0030 U+0037 U+002D U+004C U+0061 U+0079 U+0065 U+0072 U+002D U+0032 U+002E U+006D U+0064` |
| DEL-108 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0031 U+005F U+0063 U+0061 U+006E U+0061 U+0072 U+0079 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-109 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0032 U+005F U+0070 U+0075 U+0062 U+006C U+0069 U+0063 U+0061 U+0074 U+0069 U+006F U+006E U+005F U+0072 U+0065 U+0063 U+006F U+0072 U+0064 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-110 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0033 U+005F U+0065 U+0078 U+0070 U+006F U+0073 U+0075 U+0072 U+0065 U+005F U+0065 U+0076 U+0065 U+006E U+0074 U+0073 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-111 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0034 U+005F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+005F U+0070 U+0072 U+006F U+0066 U+0069 U+006C U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-112 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0035 U+005F U+0070 U+0072 U+006F U+0062 U+0065 U+005F U+0072 U+0065 U+0071 U+0075 U+0065 U+0073 U+0074 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-113 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0036 U+005F U+006D U+006F U+0064 U+0065 U+006C U+005F U+0072 U+0065 U+0073 U+0070 U+006F U+006E U+0073 U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-114 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0037 U+005F U+0063 U+006F U+006E U+0074 U+0072 U+006F U+006C U+005F U+0072 U+0065 U+0073 U+0070 U+006F U+006E U+0073 U+0065 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-115 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0038 U+005F U+006D U+0061 U+0074 U+0063 U+0068 U+005F U+0061 U+006E U+0061 U+006C U+0079 U+0073 U+0069 U+0073 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-116 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+0030 U+0039 U+005F U+0066 U+0069 U+006E U+0064 U+0069 U+006E U+0067 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-117 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0052 U+0055 U+004E U+002D U+0032 U+0030 U+0032 U+0036 U+0030 U+0039 U+0033 U+0030 U+002D U+0030 U+0032 U+0034 U+0031 U+0033 U+0039 U+002F U+0053 U+0042 U+002D U+0030 U+0030 U+0031 U+002F U+006D U+0061 U+006E U+0069 U+0066 U+0065 U+0073 U+0074 U+002E U+006A U+0073 U+006F U+006E` |
| DEL-118 | Legacy Runs & Datasets | `U+0065 U+0076 U+0069 U+0064 U+0065 U+006E U+0063 U+0065 U+002F U+0063 U+0068 U+0061 U+0069 U+006E U+002E U+006A U+0073 U+006F U+006E` |
| DEL-119 | Legacy Scripts | `U+0073 U+0063 U+0072 U+0069 U+0070 U+0074 U+0073 U+002F U+0062 U+0075 U+0069 U+006C U+0064 U+005F U+0063 U+006F U+006E U+0074 U+0072 U+006F U+006C U+005F U+0064 U+0061 U+0074 U+0061 U+0073 U+0065 U+0074 U+002E U+0070 U+0079` |
| DEL-120 | Legacy Scripts | `U+0073 U+0063 U+0072 U+0069 U+0070 U+0074 U+0073 U+002F U+0064 U+0065 U+006D U+006F U+005F U+0061 U+0070 U+0069 U+002E U+0070 U+0079` |
| DEL-121 | Legacy Scripts | `U+0073 U+0063 U+0072 U+0069 U+0070 U+0074 U+0073 U+002F U+006A U+0075 U+006C U+0065 U+0073 U+005F U+0072 U+0065 U+0076 U+0069 U+0065 U+0077 U+002E U+0070 U+0079` |
| DEL-122 | Legacy Scripts | `U+0073 U+0063 U+0072 U+0069 U+0070 U+0074 U+0073 U+002F U+0074 U+0065 U+0073 U+0074 U+0073 U+002F U+0074 U+0065 U+0073 U+0074 U+005F U+006A U+0075 U+006C U+0065 U+0073 U+005F U+0072 U+0065 U+0076 U+0069 U+0065 U+0077 U+002E U+0070 U+0079` |
| DEL-123 | Legacy Scripts | `U+0073 U+0063 U+0072 U+0069 U+0070 U+0074 U+0073 U+002F U+0076 U+0065 U+0072 U+0069 U+0066 U+0079 U+005F U+0070 U+0068 U+0061 U+0073 U+0065 U+0031 U+0031 U+005F U+0068 U+0061 U+006E U+0064 U+006F U+0066 U+0066 U+002E U+0070 U+0079` |
| DEL-124 | Legacy Scraper Assets | `U+0073 U+0072 U+0063 U+002F U+0073 U+0063 U+0072 U+0061 U+0070 U+0065 U+0072 U+002E U+006A U+0073` |
| DEL-125 | Legacy Scraper Assets | `U+0073 U+0072 U+0063 U+002F U+0075 U+0074 U+0069 U+006C U+0073 U+002F U+0066 U+0069 U+006C U+0065 U+0048 U+0065 U+006C U+0070 U+0065 U+0072 U+002E U+006A U+0073` |

---

## 6. Safe Unchanged Relative Paths (192 Files)

The following 192 paths represent core infrastructure, persistent storage, baseline contracts, API schemas, and dashboard components that are retained and safe from deletion.

#### Backend API Endpoints (backend/sb/api/) (8 files)

- `backend/sb/api/canaries.py`
- `backend/sb/api/cases.py`
- `backend/sb/api/datasets.py`
- `backend/sb/api/health.py`
- `backend/sb/api/overview.py`
- `backend/sb/api/probes.py`
- `backend/sb/api/sessions.py`
- `backend/sb/api/traffic.py`

#### CI Workflows & Governance (.github/) (3 files)

- `.github/CODEOWNERS`
- `.github/pull_request_template.md`
- `.github/workflows/backend-checks.yml`

#### Canary Token Infrastructure (backend/sb/canary/) (5 files)

- `backend/sb/canary/__init__.py`
- `backend/sb/canary/canaries.yaml`
- `backend/sb/canary/hashing.py`
- `backend/sb/canary/registry.py`
- `backend/sb/canary/seed.py`

#### Contract Fixtures (contracts/fixtures/) (20 files)

- `contracts/fixtures/CanariesResponse.json`
- `contracts/fixtures/CanaryDetail.json`
- `contracts/fixtures/Case.json`
- `contracts/fixtures/CaseEvidenceResponse.json`
- `contracts/fixtures/CaseSummaries.json`
- `contracts/fixtures/DatasetsResponse.json`
- `contracts/fixtures/DemoResetResponse.json`
- `contracts/fixtures/DemoStatus.json`
- `contracts/fixtures/EvidenceVerification.json`
- `contracts/fixtures/Health.json`
- `contracts/fixtures/Overview.json`
- `contracts/fixtures/ProbeListResponse.json`
- `contracts/fixtures/ProbeRun.json`
- `contracts/fixtures/ProbeRunResponse.json`
- `contracts/fixtures/SessionDetail.json`
- `contracts/fixtures/SessionList.json`
- `contracts/fixtures/SessionSummary.json`
- `contracts/fixtures/TrafficEvent.json`
- `contracts/fixtures/TrafficEvents.json`
- `contracts/fixtures/scraped_dataset_sample.jsonl`

#### Contract Schemas (contracts/schemas/) (37 files)

- `contracts/schemas/CanariesResponse.schema.json`
- `contracts/schemas/Canary.schema.json`
- `contracts/schemas/CanaryCounts.schema.json`
- `contracts/schemas/CanaryDetail.schema.json`
- `contracts/schemas/Case.schema.json`
- `contracts/schemas/CaseCounts.schema.json`
- `contracts/schemas/CaseEvidenceResponse.schema.json`
- `contracts/schemas/CaseSummaries.schema.json`
- `contracts/schemas/CaseSummary.schema.json`
- `contracts/schemas/Dataset.schema.json`
- `contracts/schemas/DatasetsResponse.schema.json`
- `contracts/schemas/DecisionCounts.schema.json`
- `contracts/schemas/DemoResetCheck.schema.json`
- `contracts/schemas/DemoResetResponse.schema.json`
- `contracts/schemas/DemoStatus.schema.json`
- `contracts/schemas/DemoStep.schema.json`
- `contracts/schemas/EvidenceCheck.schema.json`
- `contracts/schemas/EvidenceFile.schema.json`
- `contracts/schemas/EvidenceManifest.schema.json`
- `contracts/schemas/EvidenceObject.schema.json`
- `contracts/schemas/EvidenceVerification.schema.json`
- `contracts/schemas/ExposureEvent.schema.json`
- `contracts/schemas/Finding.schema.json`
- `contracts/schemas/Health.schema.json`
- `contracts/schemas/LadderCounts.schema.json`
- `contracts/schemas/Overview.schema.json`
- `contracts/schemas/PipelineStage.schema.json`
- `contracts/schemas/ProbeListResponse.schema.json`
- `contracts/schemas/ProbeResult.schema.json`
- `contracts/schemas/ProbeRun.schema.json`
- `contracts/schemas/ProbeRunResponse.schema.json`
- `contracts/schemas/Publication.schema.json`
- `contracts/schemas/SessionDetail.schema.json`
- `contracts/schemas/SessionList.schema.json`
- `contracts/schemas/SessionSummary.schema.json`
- `contracts/schemas/TrafficEvent.schema.json`
- `contracts/schemas/TrafficEvents.schema.json`

#### Dashboard API Client (dashboard/src/api/) (3 files)

- `dashboard/src/api/client.test.ts`
- `dashboard/src/api/client.ts`
- `dashboard/src/api/poll.ts`

#### Dashboard App & Tooling Config (dashboard/) (18 files)

- `dashboard/.gitignore`
- `dashboard/.oxlintrc.json`
- `dashboard/README.md`
- `dashboard/components.json`
- `dashboard/index.html`
- `dashboard/package-lock.json`
- `dashboard/package.json`
- `dashboard/public/favicon.svg`
- `dashboard/public/icons.svg`
- `dashboard/src/App.tsx`
- `dashboard/src/index.css`
- `dashboard/src/lib/utils.ts`
- `dashboard/src/main.tsx`
- `dashboard/src/types/contracts.ts`
- `dashboard/tsconfig.app.json`
- `dashboard/tsconfig.json`
- `dashboard/tsconfig.node.json`
- `dashboard/vite.config.ts`

#### Dashboard Components (dashboard/src/components/) (16 files)

- `dashboard/src/components/AboutModal.tsx`
- `dashboard/src/components/ApiStateNotice.tsx`
- `dashboard/src/components/DemoPanel.tsx`
- `dashboard/src/components/HoldToConfirmButton.tsx`
- `dashboard/src/components/InterrogatorCard.tsx`
- `dashboard/src/components/Layout.tsx`
- `dashboard/src/components/Logo.tsx`
- `dashboard/src/components/SessionDrawer.tsx`
- `dashboard/src/components/SkeletonTable.tsx`
- `dashboard/src/components/ui/Ferrofluid.css`
- `dashboard/src/components/ui/Ferrofluid.tsx`
- `dashboard/src/components/ui/button.tsx`
- `dashboard/src/components/ui/dialog.tsx`
- `dashboard/src/components/ui/sheet.tsx`
- `dashboard/src/components/ui/skeleton.tsx`
- `dashboard/src/components/ui/tooltip.tsx`

#### Dashboard Pages (dashboard/src/pages/) (9 files)

- `dashboard/src/pages/About.tsx`
- `dashboard/src/pages/Canaries.tsx`
- `dashboard/src/pages/CaseDetail.tsx`
- `dashboard/src/pages/Cases.tsx`
- `dashboard/src/pages/Login.tsx`
- `dashboard/src/pages/Overview.tsx`
- `dashboard/src/pages/Probes.tsx`
- `dashboard/src/pages/Traffic.tsx`
- `dashboard/src/pages/Welcome.tsx`

#### Edge Infrastructure (backend/sb/edge/) (4 files)

- `backend/sb/edge/context.py`
- `backend/sb/edge/pipeline.py`
- `backend/sb/edge/proxy.py`
- `backend/sb/edge/session.py`

#### Offense/Trap Transformation Core (backend/sb/trap/) (5 files)

- `backend/sb/trap/__init__.py`
- `backend/sb/trap/decoys.py`
- `backend/sb/trap/honeypots.py`
- `backend/sb/trap/injector.py`
- `backend/sb/trap/layer3.py`

#### Persistence & SQLite Store (backend/sb/store/) (3 files)

- `backend/sb/store/db.py`
- `backend/sb/store/schema.sql`
- `backend/sb/store/sessions.py`

#### Provenance Engine (backend/sb/provenance/) (9 files)

- `backend/sb/provenance/__init__.py`
- `backend/sb/provenance/correlate.py`
- `backend/sb/provenance/dataset.py`
- `backend/sb/provenance/doberman.py`
- `backend/sb/provenance/evidence.py`
- `backend/sb/provenance/investigate.py`
- `backend/sb/provenance/llm.py`
- `backend/sb/provenance/rag.py`
- `backend/sb/provenance/vault_s3.py`

#### Root Governance & Backend Core (13 files)

- `.env.example`
- `.gitignore`
- `Makefile`
- `README.md`
- `backend/requirements-dev.txt`
- `backend/requirements.txt`
- `backend/sb/config.py`
- `backend/sb/contracts.py`
- `backend/sb/hooks.py`
- `backend/sb/main.py`
- `index.js`
- `package-lock.json`
- `package.json`

#### Surviving Test Suites (backend/tests/) (33 files)

- `backend/tests/conftest.py`
- `backend/tests/contract/test_api_contracts.py`
- `backend/tests/e2e/conftest.py`
- `backend/tests/integration/test_api_runtime_surface.py`
- `backend/tests/integration/test_proxy.py`
- `backend/tests/integration/test_telemetry_persistence.py`
- `backend/tests/integration/test_trap_injection.py`
- `backend/tests/unit/canary/__init__.py`
- `backend/tests/unit/canary/_defs.py`
- `backend/tests/unit/canary/conftest.py`
- `backend/tests/unit/canary/test_freeze.py`
- `backend/tests/unit/canary/test_hashing.py`
- `backend/tests/unit/canary/test_prompts.py`
- `backend/tests/unit/canary/test_registry.py`
- `backend/tests/unit/canary/test_uniqueness.py`
- `backend/tests/unit/provenance/__init__.py`
- `backend/tests/unit/provenance/conftest.py`
- `backend/tests/unit/provenance/test_api.py`
- `backend/tests/unit/provenance/test_correlate.py`
- `backend/tests/unit/provenance/test_dataset.py`
- `backend/tests/unit/provenance/test_doberman.py`
- `backend/tests/unit/provenance/test_evidence.py`
- `backend/tests/unit/provenance/test_investigate.py`
- `backend/tests/unit/provenance/test_llm.py`
- `backend/tests/unit/provenance/test_rag.py`
- `backend/tests/unit/provenance/test_vault_s3.py`
- `backend/tests/unit/store/test_db.py`
- `backend/tests/unit/store/test_sessions.py`
- `backend/tests/unit/trap/__init__.py`
- `backend/tests/unit/trap/conftest.py`
- `backend/tests/unit/trap/test_injector.py`
- `backend/tests/unit/trap/test_install.py`
- `backend/tests/unit/trap/test_layer3.py`

#### Utility & Gate Scripts (scripts/) (6 files)

- `scripts/check_contracts.py`
- `scripts/check_ownership.py`
- `scripts/export_schemas.py`
- `scripts/preflight.py`
- `scripts/smoke.sh`
- `scripts/stability.py`


---

## 7. Grep Gate Requirements & Script Placeholder

- **Target Standard**: Zero forbidden tokens outside `.git`, case-insensitive.
- **Placeholder Command**:
  ```bash
  # Placeholder gate execution (to be authored by W5 post-authorization):
  scripts/grep_gate.sh <target-tree>
  ```
- **Execution Status**: `NOT RUN`. The production grep gate script will be authored by W5 during the integration phase following authorization. No fabricated outputs.

---

## 8. Reporting Sections

### 8.1 Scope vs Delivered
- **Scope**: Phase 0 planning documentation only for ScrapeBuster v3 Pure Layer 3 Full Offense. Define task cards W1-W5, proposed contracts, deletion inventory, safe unchanged paths, branch policy, and grep gate requirements.
- **Delivered**: Authored `docs/phase-reports/PHASE-0-KICKOFF.md` and `docs/phase-reports/PHASE-0.md`. Zero code edits, zero cleanup executions, zero migrations, zero dependency modifications, zero tests executed, zero builds/linters run, zero AWS operations. Baseline commit `36875140b32af4a32771696e3a2c2f06cd99e201` preserved untouched on `main`. Isolated worker branch `phase0/w5-kickoff` utilized.

### 8.2 Exit Criteria and Evidence
| ID | Criterion | Evidence / Verification Status |
|---|---|---|
| EC-01 | Authoritative PRD v3.0 available | UNVERIFIED (Supplied by user in conversation; cited by section IDs; literal text omitted) |
| EC-02 | Kickoff documentation established | UNVERIFIED (Planning records complete on worker branch; pending independent verifier sign-off) |
| EC-03 | Zero forbidden tokens outside `.git` | UNVERIFIED (Gate script placeholder defined; whole-tree grep gate NOT RUN) |
| EC-04 | Deletion inventory compiled | UNVERIFIED (125 legacy items encoded with deterministic decoding instructions; deletions NOT executed) |
| EC-05 | Safe unchanged paths cataloged | UNVERIFIED (192 retained paths listed in plain text) |
| EC-06 | Proposed contracts approved | UNVERIFIED (Contracts specified per PRD v3.0; awaiting implementation unblock) |
| EC-07 | Task cards W1-W5 assigned | UNVERIFIED (Cards drafted; sibling execution pending coordinator dispatch) |
| EC-08 | Automated test suite execution | UNVERIFIED (make check NOT RUN; test runs deferred to integration phase) |

### 8.3 AWS
`N/A no AWS this phase`
ScrapeBuster v3 Phase 0 is strictly a local planning and governance documentation phase. No cloud infrastructure, S3 buckets, Object Lock, IAM policies, or remote services are accessed, configured, or required.

### 8.4 make check
`NOT RUN`
In strict accordance with Phase 0 constraints and coordinator instructions, no test suites (`pytest`, `npm test`), linters (`ruff`, `oxlint`), formatters, or build scripts were executed. No command outputs are fabricated.

### 8.5 Deviations
1. **Resolution of Absent PRD**: Initial prompt noted absent `ScrapeBuster_L3_Full_Offense_PRD.md` v3.0. In conversation, user supplied PRD v3.0 (approved 2026-10-07), explicitly superseding all legacy v2 and hackathon documentation. Literal text is omitted from committed files to preserve grep hygiene; requirements are cited by section IDs.
2. **Dual-Origin Configuration Conflict**: Legacy master documentation assumed boot required only upstream origin. PRD PR-2 mandates that BOTH `SB_UPSTREAM_ORIGIN` and `SB_PUBLIC_BASE_URL` are required. PRD PR-2 takes precedence; dual-origin requirement is adopted.
3. **Cryptographic Chain Specification**: Older hackathon documentation referenced Merkle trees descriptively. PRD FR-7.1 explicitly standardizes on a single linear SHA-256 hash chain for audit and exposure records.
4. **Whole-Tree Grep Gate vs Legacy Deletion Inventory**: To resolve the tension between strict whole-tree grep gates and documenting legacy deletion targets, all 125 legacy paths containing forbidden components are deterministically encoded as Unicode code points with opaque evidence IDs. Retained source files are listed in plain text.
5. **No Code / No Test Execution**: All code edits, cleanup, dependency updates, and test executions intentionally omitted in Phase 0.

### 8.6 Risks
1. **Implementation Drift**: Sibling streams (W1-W4) could introduce divergent internal interfaces if changes deviate from proposed contracts prior to `phase0-integration` consolidation.
2. **Residual Forbidden Spellings**: Inadvertent introduction of legacy token spellings in comments, variable names, or test fixtures could trigger whole-tree grep gate failures during W5 integration.
3. **Upstream Network Latency / Faults**: Proxy unmutated pass-through under upstream network failure requires robust timeout configurations to prevent client request starvation.
4. **Dangling Import Breakages**: Removal of `backend/sb/demo/` requires synchronized import eradication in W1 (`main.py`) and W4 (`api/`) to maintain green integration builds.

### 8.7 Next-Phase
`BLOCKED`
Phase 1 implementation coding is strictly blocked within this dispatched worker task. Sibling streams will be coordinated upon kickoff publication, and final verification will occur on `phase0-integration` prior to `main` merge.
