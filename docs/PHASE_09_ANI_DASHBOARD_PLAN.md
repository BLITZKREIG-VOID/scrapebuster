# Phase 9 — Dashboard live API integration plan

**Owner:** ANI / Anirudh-Langy  
**Base:** updated `main` at `bca20d6`; Phase 6 contract merge `4acf4df` is an ancestor of this base.  
**Repository/location:** `BLITZKREIG-VOID/scrapebuster`, `dashboard/`.  
**Branch:** `phase/09-ani-dashboard-live-api`.

## View → API → contract → UI state map

| Dashboard view | Endpoint(s) | Frozen response contract | Loading/error behavior to implement |
|---|---|---|---|
| App shell / service health | `GET /api/v1/health`, `GET /api/v1/demo/status` | `Health`, `DemoStatus` | Show connecting/loading; show unavailable or last successful backend snapshot on error; no fabricated “fallback” state. |
| Overview / security KPIs | `GET /api/v1/overview`, `GET /api/v1/traffic/events`, `GET /api/v1/sessions` | `Overview`, `TrafficEvents`, `SessionList` | Separate loading, API error, empty telemetry and populated states; KPI values use persisted counts, not locally invented scores. |
| Traffic | `GET /api/v1/traffic/events`; session drawer `GET /api/v1/sessions/{id}` | `TrafficEvents`, `SessionDetail` | Poll only persisted events; aggregate top paths/clients from returned events; explicitly omit unavailable geo/ASN fields; show API status/errors. |
| Scraper/session detail | `GET /api/v1/sessions`, `GET /api/v1/sessions/{id}` | `SessionList`, `SessionDetail` | Show backend classification, state, request count, reasons, signals, layer path, traps, and exposed canary IDs; distinguish pending and failed lookup. |
| Canaries/exposures | `GET /api/v1/canaries`, `GET /api/v1/canaries/{id}` | `CanariesResponse`, `CanaryDetail` | Do not synthesize zero exposures when detail is loading or failed; expose empty state only after a successful response. |
| Datasets/probes | `GET /api/v1/datasets`, `GET /api/v1/probes`, `GET /api/v1/probes/{id}`, `POST /api/v1/probes/run` | `DatasetsResponse`, `ProbeListResponse`, `ProbeRun`, `ProbeRunResponse` | Display actual dataset/probe IDs, model metadata, result counts/text and failure/loading states; no guessed provider/model/latency/match values. |
| Provenance cases | `GET /api/v1/cases` (raw JSON array), `GET /api/v1/cases/{id}` | `CaseSummaries`, `Case` | Parse raw array without an envelope; display only persisted case/findings/session/probe IDs and case status. |
| Evidence | `GET /api/v1/cases/{id}/evidence`, `POST /api/v1/cases/{id}/verify` | `CaseEvidenceResponse`, `EvidenceVerification` | Distinguish unavailable evidence from empty; render persisted manifest/object/check fields and verification response. |
| Demo status/actions | `GET /api/v1/demo/status`, POST `/reset`, `/run`, `/restore-golden` | `DemoStatus`, `DemoResetResponse` | Show real step status and action errors; mock mode remains available only when explicitly selected. |

## Current dashboard findings

- Phase 6 is merged in the starting `main`; canonical Python contracts and `contracts/fixtures` are the response-shape authority.
- The existing API client defaults `VITE_API_MODE` to `mock`, so an unset env uses fabricated fixture values. Phase 9 will remove that runtime mock path rather than preserve an implicit fixture mode.
- TypeScript shapes drift from Phase 6 in health, probe run/result, evidence and demo fields. `getCases()` assumes `{cases}` though the live API returns a raw array.
- `usePoll` keeps old values after a failed request; pages generally fail to surface per-view errors. The shell network warning does not identify which view is stale.
- Overview derives incorrect traffic totals, counts sophisticated scrapers as neutralized, hard-codes canary count, and computes a made-up health score.
- Traffic includes invented actor, endpoint, geography and provider metrics that have no supporting backend endpoint.
- Canaries display a synthetic zero-exposure detail while the real request is pending/failing.
- Probe UI adds fabricated external models, counts, output classifications and latency; dataset records are not loaded from the datasets API.
- Case detail builds a fixed incident timeline and silently ignores evidence-fetch and verification errors instead of rendering persisted evidence.
- The Vite development server already proxies `/api` to the backend on `127.0.0.1:8000`.

## Implementation plan

1. Align `dashboard/src/types/contracts.ts` with the Phase 6 schemas and fixture envelopes, including root-array cases and nullable fields.
2. Make runtime API access live-only and remove the fixture-data client path. Keep response errors visible and do not catch them into mock values.
3. Add a reusable view-state component for loading, failed/unavailable, stale-last-success, and confirmed-empty states; update bounded polling errors and expose them at each view.
4. Map each view to the endpoint matrix above. Remove or relabel fabricated metrics and simulated content; derive local aggregates only from actual backend event/session/result rows.
5. Update the overview, traffic, canary, probe/dataset, case, evidence, session drawer, shell health and demo panel to display actual response fields.
6. Add frontend tests for live API requests, raw-array case decoding, and API failure without fixture fallback. Run dashboard typecheck/lint/build and contract handshake tests.
7. Run a controlled backend lifecycle (or deterministic seeded DB) and compare displayed values with API responses and direct SQL aggregates for the same run; document which browser-level checks are unverified if the local runtime cannot launch the dashboard/backend together.

## Boundaries

- Do not edit Phase 6 backend contracts or work around a contract mismatch with frontend defaults. Stop and report any verified mismatch.
- Do not invent a second dashboard or alter attack/provenance behavior.
- Poll existing APIs at bounded intervals; no new streaming transport.
