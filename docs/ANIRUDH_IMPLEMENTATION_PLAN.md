# Anirudh Implementation Plan — ScapeBusters

**Owner:** Anirudh (Ani / Anirudh-Langy in the v2 plan)
**Plan basis:** `SCAPEBUSTERS_MASTER_IMPLEMENTATION_PLAN (1).md`, Part I (v2 audited state), plus the current `main` source inspected on 2026-09-29.
**Target:** complete the backend edge and control API so the team can safely run the live CampusCart demo and show accurate, persisted results.

## 1. Outcome and boundaries

Anirudh owns the backend integration spine: FastAPI app wiring, edge pipeline, Layers 1 and 2, SQLite store, telemetry APIs, shared contracts, integration gates, and backend setup/check commands.

The intended end-to-end data path is:

```text
attack/browser → local ScapeBusters edge → CampusCart upstream
              → L1/L2/L3 decision → SQLite events + sessions
              → control/provenance APIs → dashboard in live mode
```

CampusCart is the controlled demo target. It is external to this repository. Do not create `demo_site/`, send attack traffic directly to CampusCart, or direct any test/attack at an arbitrary third-party site. Attack tools must use the local ScapeBusters edge and the agreed bounded demo settings. The dashboard is not present in this checkout; its repository and owner must be confirmed before dashboard-specific work is assigned.

The top-level `index.js`, `src/`, and Node `package.json` are the legacy scraper, not the Python ScapeBusters backend. Avoid mixing that code into these backend tasks.

## 2. Baseline and source-of-truth rule

The v2 plan's audit records `main` at `4b1f0ea`; the checkout inspected for this plan is newer (`a29d5df`, `feat(edge): implement INT-08 scraper intelligence`). Therefore, use the audit findings as a gap checklist, not as proof that every gap is still present.

In particular, current `backend/sb/edge/layer1.py` contains score bands, rate tracking, throttle/block paths, and reason codes; current `backend/sb/edge/layer2.py` contains server-side signal scoring, PASS/TRAP/RESTRICT bands, PoW verification, and signed clearance-cookie helpers. These features still need their specified acceptance behavior verified. Do not rewrite them just because the older audit described earlier implementations.

**Implementation snapshot for this branch:** session storage/API reads, L2 outcome logging, Ani-owned response models/fixtures, base Makefile cleanup, runtime ignore rules, and a backend CI workflow have been implemented. Python syntax compilation and Pydantic schema export completed. Unit/contract/integration tests and Ruff have not been run. CampusCart/router/provenance integration remains in the deferred-work register.

Before implementation:

1. Confirm the current `main` SHA and clean working tree; work on a feature branch.
2. Recheck open PR/branch state for the CampusCart integration and compare it to current `main`.
3. Read the current handlers, contracts, schema, tests, and the matching v2 plan acceptance criteria for each task below.
4. Record any decision that changes the canonical behavior in `docs/DECISIONS.md`; Part I of the v2 plan overrides its legacy Part II text.
5. Keep task changes within Anirudh's owned paths. Ask the owning teammate for changes to their subsystem rather than editing it directly.

## 3. Priority map

Use this dependency gate throughout: **do independent Anirudh work now; defer each integration or acceptance task that needs an Arnav- or Hardik-owned deliverable until that owner marks it ready.** “Ready” means the owner identifies the supported interface, the code is available on the integration branch, and relevant owner checks have been run. A file existing in the checkout is not by itself a completed handoff.

| Track | Work | Start condition |
|---|---|---|
| Do now — Ani-owned | Reconcile and complete L1/L2 behavior and Ani-owned tests; improve core event/session persistence; complete models/fixtures for Ani-owned APIs; fix base Makefile, environment/dependency documentation, ownership metadata, ignore rules, and offline-safe CI. | Does not require another owner's implementation or integration test. |
| Deferred — waits for Hardik and/or Arnav | Mount their routers; integrate trap/exposure/provenance fields; finalize their API contracts; review CampusCart proxy integration; run full CampusCart E2E and dashboard acceptance. | Named owner provides a ready handoff; record it in [ANIRUDH_DEFERRED_WORK.md](ANIRUDH_DEFERRED_WORK.md). |
| Conditional | AWS health/configuration. | Operator confirms AWS scope (OD-7) and Hardik's S3 implementation is merged and ready. |
| Blocked on operator | Dashboard live acceptance. | Dashboard repository and owner are identified (OD-6). |

## 4. Detailed work sequence

### Phase 0 — Establish the actual baseline

**Files:** `docs/DECISIONS.md`, `docs/INTEGRATION_LOG.md` (record results only after running them), current source and tests.

**Actions**

- Confirm whether the v2 plan's listed PRs still exist and whether CampusCart integration has merged. Do not assume the audit's PR status is current.
- Compare current Layer 1 and Layer 2 code to master-plan §§4–5 and task cards R-02/R-03. List any remaining behavioral differences before editing.
- Confirm the target integration configuration expected by the CampusCart branch (`UPSTREAM_ORIGIN` / fallback settings) and retain CampusCart as the only demo upstream.
- Confirm with the operator who owns the dashboard and where it lives (OD-6). Record the answer so API work has a real consumer.
- Resolve OD-1 and OD-2 only after comparing current implementation with acceptance behavior. Record whether the code will conform to the legacy spec or whether the spec is amended; do not leave conflicting behavior implicit.
- For every integration task below, check `docs/ANIRUDH_DEFERRED_WORK.md`. Do not begin its gated portion until the named owner has supplied the handoff.

**Exit criteria**

- Current commit, relevant branches/PRs, and baseline commands are recorded.
- OD-1, OD-2, OD-5, and OD-6 have a clear status; no implementation is based solely on the stale audit table.

### Phase 1 — Prepare and then mount backend routes (R-01; integration gated)

**Primary file:** `backend/sb/main.py`
**Existing route modules:** `backend/sb/api/{canaries,datasets,probes,cases,demo}.py`

**Do now**

- Record each router's import path, URL prefix, dependencies, initialization needs, and response models in the deferred-work register.
- Do not wire or adapt a router whose owner has not confirmed the interface. The `main.py` wiring itself is deferred until the owner handoffs below.

**Deferred portion — wait for owner handoffs**

Wait for Hardik to confirm the canaries, datasets, probes, and cases routers are ready to mount; wait for Arnav to confirm the demo router and its dependencies are ready. Then:

**Actions**

1. Import and mount `canaries`, `datasets`, `probes`, and `cases` routers under the existing `/api/v1` router.
2. Mount `demo.router` directly on the FastAPI app, before the catch-all route. It already declares `/api/v1/demo`; do not nest it under another `/api/v1` prefix.
3. Preserve the catch-all edge handler for website paths and keep `/api/*`, `/_sb/*`, `/health`, and static paths exempt from the protected-site pipeline as specified.
4. Add route-level coverage for representative GET and POST endpoints. A missing API must return a defined JSON/API response, never CampusCart HTML from the proxy.
5. Confirm startup/shutdown behavior still closes the proxy client and installs TrapHooks exactly once.

**Acceptance after dependencies are ready**

- All endpoint families in master-plan §I.D.2 resolve to their API handler.
- `/api/v1/demo/status` returns a demo status object; canary, dataset, probe, case, evidence, and verification endpoints return their expected JSON/status codes.
- `test_l1_ordinary_bot` no longer fails because `demo_router` is missing.

**Dependencies / ownership:** Do not change the internals of Hardik's provenance routers or Arnav's demo router as part of mounting. Request their review if wiring exposes a contract or initialization problem.

### Phase 2 — Make Layer 1 behavior match the acceptance test (R-02)

**Primary files:** `backend/sb/edge/layer1.py`, `backend/sb/edge/session.py`, `backend/sb/edge/pipeline.py`, `backend/sb/config.py`, `backend/tests/unit/edge/test_layer1.py`, `backend/tests/integration/test_l1_ordinary_bot.py`.

**Required behavior**

- Score only document requests for rate limiting; static and ScapeBusters internal endpoints must not inflate document rates.
- Apply client identity consistently using the request context/client key required by the chosen decision.
- Ordinary automation must be stopped before it receives CampusCart page content. The expected demonstration is a non-ALLOW first decision and a BLOCKED session before request 60.
- A block must have an enforced expiry. When it expires, the session must be eligible for evaluation again; malformed or absent expiry must not accidentally make a session permanently blocked.
- Keep decision and reason names inside the shared contract vocabulary.
- Keep state updates and event logging in one coherent pipeline branch so a request does not create duplicate/misleading events.

**Implementation approach**

1. Write down the expected score/reason/decision for at least ten representative cases: human browser, empty UA, HTTP-library UA, missing browser headers, known header fingerprint, soft rate threshold, hard rate threshold, repeated throttles, blocked session, expired block.
2. Compare the current table-driven implementation to these cases and R-02. Patch only differences.
3. Ensure pipeline short-circuits THROTTLE/BLOCK before calling the upstream proxy.
4. Ensure `reset_rate_state()` and session reset are reachable from the demo reset hooks without changing Hardik's trap/provenance internals.

**Acceptance**

- Unit table covers at least ten cases and validates score, reasons, state, and expiry behavior.
- The bounded ordinary-bot test reaches BLOCK before request 60 and receives zero CampusCart origin bodies.
- A normal browser path remains able to proceed to Layer 2.

Layer 1 unit-level behavior is Ani's work and can be completed now. Defer full attack acceptance if it requires Arnav's CampusCart branch or attack changes; do not modify Arnav-owned files.

### Phase 3 — Make Layer 2 behavior match the acceptance test (R-03)

**Primary files:** `backend/sb/edge/layer2.py`, `backend/sb/edge/static/challenge.js`, `backend/sb/main.py`, `backend/sb/edge/pipeline.py`, `backend/tests/unit/edge/test_layer2.py`, `backend/tests/integration/test_layer2_flow.py`.

**Required behavior**

- Issue a challenge for escalated document requests; verify challenge age, session/client binding, one-time use, and proof-of-work server-side.
- Score submitted browser signals server-side. Do not trust a client-supplied score or use signals that are absent from the actual request flow.
- Preserve the three behavior bands: human-like PASS with an `sb_clear` HMAC cookie bound to the client key; ambiguous/TRAP as a silent pass into trap state; crude automation RESTRICT with a clear reason and no upstream page.
- Enforce the `L2_NO_JS` rule and challenge expiry. Prevent clearance replay across client keys and after expiry.
- Keep the JS endpoint/path and interstitial marker consistent with the attacks and docs; don't change paths merely to match an older plan if the current integration contract intentionally differs.
- Emit a contract-valid telemetry row for challenge, pass/trap, and restrict outcomes as part of R-04.

**Acceptance**

- Valid, invalid, expired, replayed, and wrong-client PoW submissions have explicit unit coverage.
- Headless Playwright reaches CHALLENGE then RESTRICT with expected signal reasons.
- A human browser can PASS and subsequently access origin content using the signed clearance cookie.
- A stealth/sophisticated client can PASS or land in the ambiguous TRAP band; the outcome is confirmed with Arnav's controlled attack tools.

Implement and verify Ani-owned Layer 2 mechanics now. Defer attack-tool tuning and CampusCart end-to-end confirmation until Arnav supplies the ready attack/demo handoff. Defer any trap behavior changes to Hardik.

### Phase 4 — Persist events and session profiles (R-04)

**Primary files:** `backend/sb/edge/pipeline.py`, `backend/sb/edge/session.py`, `backend/sb/store/{schema.sql,db.py}`, `backend/sb/api/{traffic,sessions,overview,health}.py`, and the contracts/tests.

**Telemetry contract**

Every demo request must be explainable from persisted data: timestamp, session/client identity, path, status, layer, legal decision, score, reasons, session classification/state, and links to trap hits and canary exposures when applicable.

**Do now — independent event/session foundation**

- Persist request context and session state needed by Ani-owned L1/L2 handling, using the existing SQLite schema as the starting point.
- Make the current traffic/session APIs return truthful Ani-owned fields; remove fabricated defaults and private-manager access where possible.
- Compute Overview counts for data with an authoritative store; add persistence/API coverage for L1/L2 flows.

**Deferred portion — wait for Hardik's hook/provenance handoff**

Do not implement or assume the trap hook payload, exposure linkage, canary/case aggregation, or provenance health contract until Hardik confirms the interface and readiness. Then integrate those fields without editing Hardik's subsystem internals.

**Actions after handoff**

1. Define the trap/exposure event handoff with Hardik and map its fields to the persisted session/event representation without changing Hardik's subsystem internals.
2. Add exposure, canary, case, and provenance aggregations only after Hardik identifies the authoritative stores and response shapes.
3. Add Arnav's demo-run state only after the demo router/runner handoff; keep `/api/v1/demo` mounted at app level as described in Phase 1.
4. Coordinate reset-hook registration with the subsystem owners. Reset traffic/session/challenge/rate state deterministically, but never delete evidence bundles.

**Acceptance**

- After a human and each controlled scraper run, API rows explain the decisions and contain no invalid layer/decision values.
- Session details are database-backed and populated; exposure/session references agree.
- Overview counts equal SQL counts for the same run.
- Reopening the API after backend restart does not erase session history for the active demo run unless an explicit reset was requested.

Trap/exposure/case counts and complete cross-layer event acceptance remain deferred until Hardik's integration handoff is recorded.

### Phase 5 — Make contracts and fixtures enforce the interface (R-05)

**Primary files:** `backend/sb/contracts.py`, `contracts/schemas/`, `contracts/fixtures/`, `scripts/export_schemas.py`, `scripts/check_contracts.py`, `backend/tests/contract/`.

**Do now**

- Complete models and fixtures for Ani-owned `Health`, `TrafficEvent`, `SessionSummary`, `SessionDetail`, and `Overview` responses.
- Make the contract checker fail when expected Ani-owned fixtures are missing.
- Export and validate schemas for the stable Ani-owned models.

**Deferred portion — owner-approved response shapes required**

Do not finalize `Canary`, `Dataset`, `Probe`, `Case`, `Evidence`, `Verify`, or `DemoStatus` contracts from guesses. Obtain Hardik's and Arnav's agreed response shapes first, then add those models and fixtures with their review.

**Actions after handoff**

- Define a single Pydantic model for each public response: `Health` with components, `Overview`, `TrafficEvent`, session summary/detail, canary, dataset, probe run/result, case summary/detail, evidence object/manifest/receipt, verify response, and demo status.
- Remove duplicate/ad hoc public response models from API modules or have those APIs use the canonical contract models.
- Export JSON schemas from the canonical models and check them into `contracts/schemas/`.
- Add realistic JSON fixture(s) for every GET response family, including a post-attack/post-case state. Keep fixture data synthetic and free of real secrets.
- Change `scripts/check_contracts.py` so zero fixtures or missing expected fixture/model families is a failure, not a successful no-op. Validate list and envelope shapes deliberately.
- Add live API contract tests for all reachable GETs and validate error/status behavior for important POST endpoints.
- Use the existing `X-SB-Contract: 1` version convention if the API contract version is implemented; coordinate version changes with the dashboard owner.

**Acceptance**

- Contract check validates at least one fixture for every GET response model and fails if the expected fixture set is incomplete.
- Live API responses validate against the same models used to export schemas.
- Dashboard and backend consume the same field names and enum values.

The all-endpoint contract gate remains deferred until the external response shapes are ready.

### Phase 6 — Review the CampusCart integration (R-06)

**Primary files to review:** `backend/sb/config.py`, `backend/sb/edge/proxy.py`; Arnav's CampusCart branch may also change `backend/sb/trap/injector.py`, `attacks/common.py`, preflight, and smoke tooling.

**Deferred until Arnav marks CampusCart integration ready for review**

CampusCart target selection, attack/site profile, and CampusCart integration branch are Arnav's work. Do not implement a parallel origin integration or retarget his attack scripts. Record the branch/PR and request the review handoff; then perform only the Ani-owned proxy/config review below. This does not authorize merging.

**Actions after handoff**

- Confirm the CampusCart change is still on the expected branch/PR and inspect the diff against current `main` before approving anything.
- Review only your owned proxy/config changes: upstream base URL, Host/forwarding headers, identity encoding for response transformation, redirect handling, cookies, HEAD/OPTIONS, query/path preservation, timeout/error behavior, and SPA fallback responses.
- Verify that attack scripts and browser checks point at the local edge and have bounded/safe demo settings. No direct attack requests to the external upstream.
- Ask Hardik to review injector changes and Arnav to confirm the attack/demo profile. Do not merge or push without the repository owner's merge decision.
- Record actual review/merge result in `docs/INTEGRATION_LOG.md` and update plan status only when there is evidence.

**Acceptance**

- CampusCart pages load through the edge; allowed headers/cookies and response bodies behave as intended.
- Edge-owned trap/robots behavior does not expose canaries to human/control sessions.
- Upstream outage or rate-limit response is surfaced safely and stops the demo attack step instead of causing a retry loop.

### Phase 7 — Complete base developer commands and environment (R-13, R-19 support)

**Primary files:** `Makefile`, `.env.example`, `backend/requirements*.txt`, `.gitignore`, `.github/CODEOWNERS`, `.github/workflows/`.

**Actions**

- Remove or replace the `site` target that starts the absent `demo_site.app`; CampusCart is the upstream.
- Make base targets accurate and usable: `setup`, `backend`, `test-unit`, `test-contract`, `test-integration`, and `check`. Do not make base `check` depend on an absent `dashboard/`; add the dashboard command only after OD-6 identifies its location.
- Keep Arnav-owned `demo`, `preflight`, `e2e`, reset, and golden-run recipes with Arnav; coordinate interfaces rather than implementing his task cards.
- Put backend runtime dependencies in `requirements.txt` and attack/dev-only dependencies in the appropriate dev file. Include imports actually needed by the selected merged code (e.g. PyYAML); add boto3 only with the S3 implementation/decision. Verify from a clean environment.
- Add `evidence/`, `data/datasets/`, `data/golden/`, database/runtime artifacts, and local `.env` to `.gitignore` as appropriate. Never commit credentials or generated attack output.
- Replace placeholder CODEOWNERS identities/obsolete paths with confirmed handles and current paths; retain cross-owner approval for trap/demo files.
- Add CI for lint, unit, contract, and integration checks; avoid requiring live CampusCart, Ollama, AWS, or browser downloads for the ordinary PR gate.

**Acceptance**

- Base setup and `make check` work without referring to missing directories.
- Clean-environment dependency install and core checks are reproducible.
- CI runs the same offline-safe checks on a PR; no secrets are required.

### Phase 8 — AWS integration (R-13; conditional P1-high)

Defer until Hardik marks the S3 implementation ready and the operator confirms AWS is in scope (OD-7). Do not build an alternate uploader, change Hardik's vault internals, or configure credentials.

- Read `SB_S3_BUCKET` and `AWS_REGION` through centralized config; do not embed credentials or account IDs.
- Add boto3 to runtime dependencies only when the merged S3 path imports it.
- Report S3 health honestly as disabled, healthy, or unavailable; an AWS failure must not stop local evidence preservation or the demo.
- Coordinate `Health.components` with Hardik so S3 status reflects the actual vault implementation.
- Leave DynamoDB/SNS optional and off the P0 path unless the operator explicitly promotes them.

## 5. Verification checklist for Anirudh's handoff

The plan requires actual command output on the task/PR and a statement of what was not verified. Run checks only when implementing the relevant work; this document itself does not claim they have passed.

Suggested local sequence for Ani-owned, offline-safe checks (from the repository root):

```powershell
$env:PYTHONPATH = "backend"
python -m ruff check backend scripts attacks
python -m pytest backend/tests/unit/ -q
python -m pytest backend/tests/contract/ -q
python scripts/check_contracts.py
python scripts/check_ownership.py
```

Run cross-owner integration tests only after the relevant handoff is ready; then coordinate them with the owning teammate. When the route wiring, CampusCart branch, control dataset, attack safety guard, and demo laptop environment are ready, coordinate the controlled E2E with Arnav and Hardik. Do not run live attack traffic as part of routine unit/contract CI.

For every PR, report:

1. **Changed:** files and behavior.
2. **Verified:** exact commands and actual pass/fail output.
3. **Not verified:** live CampusCart behavior, Playwright, Ollama, dashboard, or AWS checks not actually run.
4. **Integration:** required reviewers, contract changes, and any decision-log updates.

## 6. Explicitly out of Anirudh's implementation scope

- Building or hosting a replacement demo website; CampusCart is the external target.
- Implementing the dashboard while its repository and owner are unresolved.
- Editing Hardik's trap, canary, or provenance internals, or Arnav's attack/demo internals, without an owner-approved change request.
- AWS credentials, S3 bucket setup, or account provisioning.
- P2 features such as multi-site support, TLS JA3/JA4, commercial model probing, or production deployment architecture.

If an Ani-owned task is blocked by one of these owner deliverables, defer the integration portion and keep it listed in `docs/ANIRUDH_DEFERRED_WORK.md`; do not silently drop it or implement around an unconfirmed interface.

## 7. Definition of done for Anirudh

- Required API and demo routes are mounted and API paths cannot fall through to the CampusCart proxy.
- L1 and L2 acceptance behaviors are demonstrated by tests; blocked/restricted requests receive no origin content.
- Traffic, session state, trap references, and overview values are persisted and API-visible with legal contract values.
- Contracts and fixture checks are complete and non-vacuous; live responses validate against them.
- CampusCart integration has been reviewed and validated through the local edge, with cross-owner changes approved by their owners.
- Core commands and offline-safe CI are reproducible; environment, ownership, and generated-data rules reflect the current repository.
- Integration log and handoff record exact evidence, remaining limitations, and any decisions still owned by the team.
