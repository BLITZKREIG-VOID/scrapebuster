# Phase 6 — Shared Contract Freeze Plan

**Owner:** ANI / Anirudh-Langy
**Base:** `main` at `4e4ad93` (Phase 5 PR #28 merge SHA, fetched and checked out before branching)
**Work branch:** `phase/06-ani-contract-freeze`

## Current live-response findings

The mounted app was queried through FastAPI `TestClient` after Phase 5, with a fresh SQLite database and seeded canaries. The sampled responses were live handler responses, not fixtures:

- `/api/v1/health`: `{status, components}`; component status values were `ok` and `not_checked`.
- `/api/v1/overview`: decision/session/canary/case counts came from SQLite; `latest_case` was `null` with no cases; pipeline statuses were `ok`/`unknown`.
- `/api/v1/traffic/events`: `{events: [], last_seq: 0}` when empty; Phase 5 emits L1/L2/L3/ORIGIN event layers and legal decision literals.
- `/api/v1/sessions`: `{sessions: []}` when empty; `/sessions/{id}` returns the persisted detail fields.
- `/api/v1/canaries`: `{canaries: [...]}`; `/canaries/{id}` adds nullable `publication` and `exposures`.
- `/api/v1/datasets`: `{datasets: [...]}`; `/api/v1/probes`: `{probes: [...]}`; `/api/v1/cases` is a raw JSON array.
- `/api/v1/demo/status`: `{run_id, phase, mode, steps}`; `run_id` is `null` before reset, and each of seven steps carries nullable `started_at`/`finished_at`.

The current contract test file validates only four API families (health, traffic, sessions, overview). `contracts/fixtures` has seven JSON files, no demo-status fixture, and no canary/dataset/probe/case/evidence response fixtures. `scripts/check_contracts.py` checks for seven names, but validates each array by validating its members individually; it does not validate an array response as one canonical API shape. Canary, dataset, probe, evidence, and demo response classes are currently local to API modules or untyped dictionaries.

## Implementation plan

### Canonical response models

Keep response JSON shape unchanged; centralize response models in `backend/sb/contracts.py` and have routers import them:

| API response shape | Canonical model |
|---|---|
| Health | `Health` with named component statuses |
| Overview | `Overview`, explicit decision counts, ladder counts, canary counts, case counts, nullable `latest_case` |
| Traffic events | `TrafficEvents` / `TrafficEvent` |
| Session list/detail | `SessionList` / `SessionSummary` / `SessionDetail`, typed layer-path entries |
| Canaries list/detail | `CanariesResponse` / `CanaryDetail` / `Canary` / `Publication` / `ExposureEvent` |
| Dataset list and ingest result | `DatasetsResponse` / `Dataset` |
| Probe list/detail/run result | `ProbeListResponse` / `ProbeRun` / `ProbeResult` / `ProbeRunResponse` |
| Cases list/detail | `CaseSummaries` root array / `CaseSummary` / `Case` / `Finding` |
| Case evidence | `CaseEvidenceResponse` / `EvidenceManifest` / `EvidenceFile` / `EvidenceObject` |
| Evidence verification | `EvidenceVerification` / `EvidenceCheck` |
| Demo status and run response | `DemoStatus` / `DemoStep`; reset gets a typed response/check model |

Overview counts are non-null integers on live Phase 5 code. `latest_case`, `DemoStatus.run_id`, demo step timestamps, canary publication time, evidence receipt, and exposure referer/accept-language remain intentionally nullable because live handlers can return `null`/omit those facts. Keep variable provenance `Finding` detail maps and optional external S3 receipt payloads flexible and document why.

### Fixtures and schemas

- Add a non-empty, synthetic JSON fixture for each dashboard-facing GET response shape in the endpoint map, plus representative probe-run, dataset-ingest, demo-reset, and evidence-verification responses consumed by E2E/actions.
- Keep synthetic values clearly fictional and use no credentials, deployed URLs, operator data, or secret canary values.
- Preserve current API semantics: notably the raw-array case-list response, nested `canaries`/`datasets`/`probes` envelopes, and optional/null fields observed live.
- Export JSON Schemas for the canonical models with `scripts/export_schemas.py`; remove stale schemas only when the model has moved/been renamed canonically.
- Extend the checker with an explicit required response-fixture manifest and validate each whole fixture using `model_validate`, including root arrays. Fail for an empty fixture directory, missing required fixture, missing model, invalid JSON, or response/model mismatch.

### Live contract gate

Extend `backend/tests/contract/test_api_contracts.py` to exercise the mounted app against a temporary SQLite DB and actual handlers. Seed representative canary, dataset, probe, session/event, case, and evidence rows/files through the owning stores or DB schema. Validate every relevant GET response and the evidence-verification POST against canonical models; keep 404/409 error assertions separate from success contracts. For list endpoints, seed at least one row so tests cannot pass vacuously. Assert raw case-list response remains an array and response keys match the canonical model.

Required route matrix: health, overview, traffic events, session list/detail, canary list/detail, dataset list, probe list/detail, case list/detail, case evidence, demo status, and evidence verification. Probe run and dataset ingestion success shapes are covered by fixture/model validation; do not invoke external LLM/AWS services from contract tests.

### Compatibility/freeze constraints

- Do not change live response fields to satisfy stale fixtures. Treat the sampled Phase 5 responses and master-plan §I.D.2 as authoritative.
- Keep API JSON values and wrappers stable so Hardik's provenance clients, Arnav's E2E runner, and the dashboard can share these definitions without duplicated frontend types.
- Avoid touching decision logic, telemetry persistence, provenance algorithms, dashboard code, or external service behavior.
- Once merged, `contracts.py`, `contracts/schemas`, `contracts/fixtures`, and contract fixtures are frozen; follow-up shape changes require a separately reviewed contract-change PR.

## Baseline checks

- `scripts/check_contracts.py`: passes current seven fixtures, but coverage is incomplete.
- `backend/tests/contract/test_api_contracts.py`: 4 passed; it covers only health, traffic, sessions, and overview.
- Worktree was clean on updated `main` before creating this branch.
