# ScrapeBuster v3 — Outstanding Work and Acceptance Ledger

**Recorded:** 2026-10-10. **Status:** OPEN. **Integration authority:** Supervisor. **Implementation ownership:** one assigned worker per writable file set; `@verifier` is independent and read-only. **Authoritative rules:** user-supplied v3 PRD first, current mission second, historical worker task specifications only when compatible.

This document is a recovery checkpoint, not proof of phase acceptance. The historical Orca task for Phase 2 contains superseded thresholds and a latency target; these are not acceptance criteria. Read the actual PRD before accepting further work. The PRD source file was not present in the accessible main tree during this checkpoint.

## Recovery facts and immediate decisions

| ID | Item | Owner | Dependency / acceptance | Status |
| --- | --- | --- | --- | --- |
| R01 | Preserve existing Git state and Phase 2 edits, including untracked files | Supervisor | No reset, cleanup, rebase, or replacement of preserved branch; direct inspection of its status and diff | **BLOCKED:** Phase 2 worktree is outside the approved `/scrapebuster` tool root; do not attempt indirect writes |
| R02 | Reconcile Orca workers and dispatch history | Supervisor | Inspect worker-list, worker-show and terminal observations; follow documented recovery; settle only on positive evidence | **OPEN:** `ctx_5cde11a4ff5a` has `unverifiable/stale_status` agent liveness and live/orphaned terminal showing **AI: Out of credits**; `ctx_27f584d8d9af` is failed/exited and retained. Attempted eligible release twice; both commands were blocked before Orca execution, leaving resource intact |
| R03 | Verify evidence files in Phase 1 and Phase 2 evidence directories | QA integration owner | Inventory originals, timestamps, hashes, manifests, logs; preserve historical failed results | **BLOCKED:** evidence folders outside connected root |
| R04 | Confirm canonical PRD against current mission and record conflicts | Supervisor | PRD v3.0 sections, original master prompt, all open gates reconciled | **OPEN:** full original PRD unavailable in connected root |
| R05 | Allocate edit ownership and independent verifier | Supervisor | One integration owner, no overlapping writer assignments; report verifier's exact scope and result | **OPEN:** Phase 2 files fenced from new edits pending live ownership resolution |

## Phase 1 — Missing closure (gate before Phase 2 acceptance)

| ID | Item | Owner | Acceptance and evidence | Depends on | Status |
| --- | --- | --- | --- | --- | --- |
| P1-01 | Verify integrated Phase 1 tree at `329a7586cc62924a032827546428cdb936884433` | Phase 1 integration owner | Clean branch, actual code contracts, `make check` and phase-specific requirements checked | R03, R04 | OPEN |
| P1-02 | Validate historical 185-test and telemetry benchmark reports | QA owner | Read final manifest and logs, verify hashes, test count, chain, achieved concurrency, and limitations; do not call tap-only measurement full proxy overhead | R03 | OPEN |
| P1-03 | File `docs/phase-reports/PHASE-1.md` in integration branch | Integration owner | Seven required report sections: scope/commits, mapped criteria, tests, AWS N/A, PRD decisions, risks, readiness | P1-01, P1-02 | MISSING |
| P1-04 | Independent `@verifier` inspection of exact Phase 1 integrated worktree/commit | Independent verifier | Read-only acceptance decision and actionable findings backed by source and evidence | P1-03 | OPEN |
| P1-05 | Merge accepted Phase 1 into main and record merge commit | Supervisor / sole integration owner | Gate passes, main diff and histories verified, all reports committed, no lost changes | P1-04 | OPEN; main still `3611b0e` at checkpoint |

## Phase 2 — Adaptive asset ratio and routing

**Kickoff scope:** Resume original worktree `C:/Users/kashy/orca/workspaces/scrapebuster/phase2-implementation` (branch `phase2-implementation`, baseline `329a758`). **Implementation owner:** recovered Phase 2 worker after liveness resolution, otherwise one replacement specifically authorized for this file set. **Contracts/UI/tests owner:** separately assigned worker only on a nonoverlapping path set; integration remains single-owner. **Independent gate:** `@verifier`.

| ID | Item | Acceptance and evidence | Depends on | Status |
| --- | --- | --- | --- | --- |
| P2-01 | Resume and inspect original modifications before coding | Inventory tracked/untracked source and report existing fixes; no wholesale rewrite | R01, R02, R04 | BLOCKED |
| P2-02 | EMA, trust, maturity and cold start | Route-isolated EMA `alpha * current + (1-alpha) * historical`, default alpha .2; 0–100 trust score; conservative configurable maturity; cold starts watermarked | P2-01 | OPEN |
| P2-03 | Durable state and anomaly lock | Configurable default 20 consecutive API calls at approximately zero AR; sticky sandbox across routes/restarts; Redis with SQLite fallback; truthful sessions/metrics | P2-02 | OPEN |
| P2-04 | Strict routing and mutation policy | Adaptive default and `always` mode; high trust fast path has identical origin bytes and never invokes mutation; sandbox mutation uses registry; classifier faults retain deterministic watermark | P2-03 | OPEN |
| P2-05 | Background persistence | Startup, shutdown drain, reset, failure visibility; persistence off protected critical path; decisions/faults chained | P2-03 | OPEN |
| P2-06 | Real route/trust/routing API and dashboard | Durable query-backed endpoints and accurate displayed baselines, decisions, locks, trust state | P2-04, P2-05 | OPEN |
| P2-07 | Configuration and meaningful tests | `.env.example`, EMA, maturity, organic/harvester, lock threshold, restart, byte equality/no mutation, registry, fallback, persistence and existing suite | P2-02–P2-06 | OPEN |
| P2-08 | Full proxy benchmark, not just classifier/tap | Real origin, lifecycle, warmup and verified branches; scheduled 500 req/s concurrency; achieved RPS, duration, error/backlog, counts; defensible per-request p95 added fast <5 ms, sandbox <50 ms | P2-07 | OPEN; historical fast 248.288 ms, sandbox 282.042 ms remain failed evidence |
| P2-09 | Phase 2 evidence and `PHASE-2.md` | Preserve old failures; timestamped command/status/log/hash manifest; tests and benchmark results, decisions, risks, AWS N/A, commit range | P2-08 | OPEN |
| P2-10 | Independent gate, commit and merge | Phase 2 branch commit; verifier on exact integrated worktree and evidence; merge only after acceptance | P1-05, P2-09 | OPEN |

## Phase 3 — Watermarks, KB and RAG

**Owner:** designated offense/KB implementation worker; contracts/UI worker owns separate paths; one integration owner; read-only `@verifier`.

| ID | Item | Acceptance and evidence | Depends on | Status |
| --- | --- | --- | --- | --- |
| P3-01 | Watermark vector matrix | Additive/schema-valid JSON synthetic records, HTML visible linguistic and JSON-LD vectors, beacon and honey key, three or more session-bound registry vectors | P2-10 | NOT STARTED |
| P3-02 | Distribution and rendering safety | Placement randomized across 100 sessions; HTML and JSON parsing/rendering safety and no cross-session binding | P3-01 | NOT STARTED |
| P3-03 | Configurable, offline-capable KB/RAG | Local vector store, configured external backend, catalog/brand/schema ingestion API/UI; source fidelity and deterministic offline fallback | P3-01 | NOT STARTED |
| P3-04 | Session cache, resiliency, latency | Cached mutations; response remains watermarked on RAG/primary mutation failure; sandbox proxy latency budget validated | P3-03 | NOT STARTED |
| P3-05 | Integration evidence, human review and report | KB samples, visual review screenshots, validation tests, `make check`, `PHASE-3.md`, independent acceptance | P3-01–P3-04 | NOT STARTED |

## Phase 4 — Callbacks, probes and forensic correlation

**Owner:** designated callback/probe worker; API/UI assigned separately; one integration owner; read-only `@verifier`.

| ID | Item | Acceptance and evidence | Depends on | Status |
| --- | --- | --- | --- | --- |
| P4-01 | Registry-correlated callbacks | Image callback delivers 1×1 pixel; honey key interception, complete request metadata; exempt callback routes from mutation; persist and chain events | P3-05 | NOT STARTED |
| P4-02 | Configurable probes | Targets and prompt sequences, request/response/control/match transcripts, automatic case linking for verbatim positive | P4-01 | NOT STARTED |
| P4-03 | Live UI/API and offline scraper-processing harness | True callback/probe/case state queried by dashboard and endpoints | P4-01, P4-02 | NOT STARTED |
| P4-04 | Proven correlation demonstrations | Scrape-process-correlated callback within 5 sec; honey key capture; positive mock RAG verbatim match, VALID forensic chain | P4-03 | NOT STARTED |
| P4-05 | Report and gate | `PHASE-4.md`, `make check`, timestamped evidence manifest, verifier acceptance; DNS optional | P4-04 | NOT STARTED |

## Phase 5 — Local evidence vault and authorized S3 Object Lock

**Owner:** provenance/vault implementation worker, separately owned UI, one integration owner, independent verifier. **AWS authority:** operator approval for precise infrastructure changes.

| ID | Item | Acceptance and evidence | Depends on | Status |
| --- | --- | --- | --- | --- |
| P5-01 | Local evidence bundles, manifests and offline verification | Per-case downloadable bundles; verify CLI and API; tampering reported TAMPERED, untampered VALID; explicit PRESERVED_LOCAL | P4-05 | NOT STARTED |
| P5-02 | Real S3 Object Lock integration | Upload with checksums, version ID, retain-until and retention mode; no locked-success claim without S3 verification; explicit failure modes | P5-01 | NOT STARTED |
| P5-03 | Obtain AWS approval and implement least privilege | Operator reviews exact resources, IAM JSON, retention and rollback before infrastructure writes; do not expose credentials | P5-02 | NEEDS OPERATOR AUTHORIZATION |
| P5-04 | Actual AWS and UI acceptance | Real authorized upload, version metadata, retention, early-delete denial under tested principal, receipts, download/verify UI | P5-03 | BLOCKED UNTIL APPROVAL/ACCESS |
| P5-05 | Mandatory AWS Setup Report and independent gate | `PHASE-5.md`, actual identifiers as permitted, commands and genuine outputs, environment mapping and rollback; `make check`, independent acceptance | P5-04 | NOT STARTED |

## Phase 6 — Installable package and documented operator workflow

**Owner:** packaging/QA worker; single integration owner; independent verifier.

| ID | Item | Acceptance and evidence | Depends on | Status |
| --- | --- | --- | --- | --- |
| P6-01 | Python package, CLI and dashboard | Installable `scrapebuster`; serve, doctor, demo run/reset, evidence verify; OpenAPI export and dashboard | P5-05 | NOT STARTED |
| P6-02 | Containers and configuration | Multi-stage Dockerfile, Compose/supporting services, one-container demo and complete `.env.example` | P6-01 | NOT STARTED |
| P6-03 | Site-agnostic operator setup | Ten-section `docs/SETUP_GUIDE.md`, neutral origin configuration, troubleshooting and passive-trapping legal guidance | P6-02 | NOT STARTED |
| P6-04 | Fresh install acceptance and report | Clean pip install/boot, Docker/Compose, local complete loop, doctor, repeatable reset, fresh operator timed trial, clean-clone `make check`, `PHASE-6.md` and independent verdict | P6-03 | NOT STARTED |

## Phase 7 — Live deployment and final acceptance

**Owner:** one release/integration owner, designated test/evidence owner, independent final verifier. **Authorization:** operator approves prepared-site deployment and any external infrastructure change.

| ID | Item | Acceptance and evidence | Depends on | Status |
| --- | --- | --- | --- | --- |
| P7-01 | Approved deployment and site KB | Actual prepared site configured without code-specific branding/origin; operator authorization and real live endpoints | P6-04 | NEEDS DEPLOYMENT AUTHORIZATION |
| P7-02 | Full live offense narrative | Untouched high-trust organic response, sandboxed harvester, registry-bound trap, timely externally reachable callback, verbatim probe match, valid local evidence and real S3 receipt | P7-01 | NOT STARTED |
| P7-03 | Genuine delivery artifacts | Live logs, transcripts, external-network reachability, timing, screenshots, hashes, receipts, repeatable reset, legacy cleanup, final `make check` | P7-02 | NOT STARTED |
| P7-04 | Final published reports | `PHASE-7.md`, deployment AWS Setup Report, compiled requirement-to-evidence MVP report | P7-03 | NOT STARTED |
| P7-05 | Independent final acceptance and merge/deployment reconciliation | Verifier reviews exact final commit and deployed system; every prior report accepted, clean-clone passes, no fabricated evidence | P7-04 | NOT STARTED |

## Global gates

Each phase needs kickoff ownership and interfaces; implementation and tests; frozen bounded verification with `make check`; command, absolute worktree, time, exit, stdout/stderr, hashes, counts, commit/tree; preserved failures; seven-part report; independent read-only verdict; integration into `main`; only then next phase. Phases through 4 remain AWS-free. No external infrastructure writes until authorized. A phase with missing evidence is explicitly unaccepted.

## Current access and evidence gap

The connected coding tool currently approves only `/scrapebuster` and `/skills`. An attempt to use `C:/Users/kashy/orca/workspaces/scrapebuster/phase2-implementation` as the working directory was rejected before execution as outside the approved root. The similarly located Phase 1 integration and evidence folders cannot be directly inspected through this connection. Reconnect the Orca project workspace containing these worktrees, or add the named worktree/evidence roots to this session's approved paths. The current Antigravity Phase 2 agent additionally reports exhausted AI credits; resolve its model/account capacity before attempting further edits. Until worktree access and dispatch ownership are settled, no worker should replace the live/unverifiable Phase 2 dispatch or edit its preserved files.
