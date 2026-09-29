# Anirudh Deferred Work Register

This register accompanies [`ANIRUDH_IMPLEMENTATION_PLAN.md`](ANIRUDH_IMPLEMENTATION_PLAN.md). It records Anirudh-owned work that must wait for an Arnav- or Hardik-owned implementation, interface, decision, or validation. **Deferred means paused at the dependency boundary, not cancelled.**

## Handoff rule

Do not start a deferred integration task merely because the other owner's files exist. Resume it when the owner:

1. Identifies the branch/commit containing the intended change.
2. Confirms the supported interface and any configuration needed by Anirudh.
3. Provides the relevant check output or explicitly identifies what remains unverified.
4. Confirms any cross-owner behavior that affects their subsystem.

Record the handoff date, commit/PR, interface notes, and verification evidence in `docs/INTEGRATION_LOG.md`. Anirudh then works only in Ani-owned paths unless the file owner explicitly requests/reviews a change.

## Deferred items

| ID | State | Anirudh work being deferred | Dependency owner and handoff | Resume when | Anirudh deliverable after resume |
|---|---|---|---|---|---|
| D-01 / R-01 | WAITING | Mount canaries, datasets, probes, cases, and demo routers in `backend/sb/main.py`. | Hardik confirms the four provenance routers and their startup requirements; Arnav confirms the demo router's interface/dependencies. | Both router groups have a supported interface available on the integration branch. | Mount provenance routers once under `/api/v1`; mount demo router directly on `app` before catch-all; verify paths return API JSON rather than proxied HTML. |
| D-02 / R-04 | WAITING | Integrate trap hits, exposure-to-session links, canary/case overview counts, and full cross-layer telemetry. | Hardik confirms the TrapHooks/exposure data shape and write lifecycle; Arnav supplies the controlled-run sequence/profile where needed. | Hook and exposure interfaces are stable, and an owner can provide a representative run. | Wire persisted references using existing stores/contracts; make event, session, and overview endpoints agree with the same run. Do not edit `backend/sb/trap/`, `canary/`, or `provenance/` internals. |
| D-03 / R-05 | WAITING | Final contracts, schemas, and fixtures for provenance, evidence, verification, and demo responses. | Hardik supplies canonical provenance response shapes; Arnav supplies canonical `DemoStatus` and demo API shapes. | Both owners agree the response models/field semantics are stable. | Add canonical Pydantic models, export schemas, add fixtures, and validate live responses. Keep Ani-owned Health/Traffic/Session/Overview models moving independently. |
| D-04 / R-06 | WAITING | Review CampusCart integration changes in `proxy.py`/`config.py` and validate the merged origin behavior. | Arnav provides the intended CampusCart branch/PR and safe-demo configuration; Hardik reviews injector changes. | Arnav asks for review on a current diff against the integration base and the cross-owner review path is clear. | Review only Ani-owned files; confirm upstream forwarding, redirects, cookies, methods, SPA responses, and failure behavior. Record review; repository owner decides whether/when to merge. |
| D-05 / R-02/R-03 integration acceptance | WAITING | Validate ordinary bot, advanced automation, sophisticated scraper, and human-control outcomes as one demo profile. | Arnav supplies the ready CampusCart site profile and bounded attack scripts; Hardik supplies trap behavior for sophisticated scraper. | Scripts use the local edge, have safe request bounds, and the required trap path is available. | Run coordinated acceptance; fix Ani-owned edge behavior only. Any script/site/trap changes return to their owner. |
| D-06 / R-04 health components | WAITING | Report LLM and S3 health accurately in the health response. | Hardik supplies the supported component health interface and confirms S3 implementation status; operator decides whether AWS is in scope. | Component states and the expected meaning of `disabled`, `ok`, and `down` are agreed. | Add/maintain the API model and aggregation on Ani-owned API/config paths; do not implement the LLM or S3 subsystem. |
| D-07 / R-13 AWS runtime integration | WAITING | Add centralized AWS settings, dependency wiring, and health reporting for S3. | Hardik's S3 implementation is reviewed/merged; operator confirms OD-7 and provides AWS setup outside the repository. | S3 module/interface is stable and AWS is explicitly in scope. | Wire config/dependency/health behavior; verify disabled mode remains local-only. No credentials or account secrets enter the repo. |
| D-08 / R-15/R-17 E2E and repeatability sign-off | WAITING | Sign off the complete live demo, repeatability, and golden-run integrations from the backend side. | Arnav owns attack runner, preflight, reset/golden commands, safe-mode guards, and E2E orchestration; Hardik owns real control/provenance data and stability. | R-01 through R-06 dependencies are cleared, the real control dataset exists, and owners agree a demo run is safe to execute. | Support the coordinated run; confirm backend telemetry/API values against persisted records; record results and unresolved issues. Do not claim E2E complete from unit tests alone. |
| D-09 / R-16 | WAITING | Validate backend-to-dashboard live data and counts. | Operator identifies dashboard repository and owner (OD-6); dashboard owner confirms API client and expected model versions. | Dashboard is available in live mode with no fixture fallback. | Compare each displayed count/detail with the API and database for the same run; coordinate only Ani-owned API/model fixes. |
| D-10 / R-19 | WAITING | Recheck and clear the Ruff findings in owner-specific tests/scripts, then expand lint coverage to the full repository. The v2 audit recorded 12 Ruff errors; that count must be rechecked against the current branch. | Arnav owns E2E test/preflight/smoke files; Hardik owns stability/provenance/test files. | Each owner confirms the lint fixes or approves Ani's narrow cross-owner patch. | Remove current lint errors and restore full-scope `ruff check backend scripts attacks` in local and CI gates. Until then CI lints Ani-owned backend files only. |
| D-11 / R-19 | WAITING | Replace placeholder CODEOWNERS handles with verified GitHub identities. | Operator/team confirms the actual GitHub handles for Ani, Arnav, Hardik, and dashboard owner. | Handles are verified against the GitHub accounts/team. | Update ownership rules without guessing usernames and verify the ownership checker maps the current author correctly. |

## Resume order

1. **Router handoffs (D-01)** unblock API access to provenance and demo functions.
2. **Trap/exposure and live telemetry handoffs (D-02, D-05)** unblock persisted full-session stories.
3. **Response shapes (D-03)** lock the API contract across owners.
4. **CampusCart integration review (D-04)** confirms the edge is connected to the chosen target.
5. **Real data and demo readiness (D-06, D-08)** unblock full E2E and repeatability.
6. **Dashboard owner confirmation (D-09)** enables final live-view acceptance. AWS work (D-07) remains conditional and can run separately after Hardik/operator handoff.

## Do not put in the deferred queue

These are independent Anirudh tasks and should continue under `ANIRUDH_IMPLEMENTATION_PLAN.md`:

- Reconcile current Layer 1 and Layer 2 implementation against the acceptance criteria, record OD-1/OD-2 decisions, and complete Ani-owned unit-level behavior.
- Persist the Ani-owned L1/L2 request/session fields and make current Ani-owned APIs return real values rather than fabricated defaults.
- Complete Ani-owned Health, TrafficEvent, SessionSummary, SessionDetail, and Overview contracts/fixtures; make their fixture checks non-vacuous.
- Fix base developer commands so they do not invoke the absent `demo_site/` or `dashboard/` as required dependencies.
- Correct owned dependency declarations, runtime ignore rules, confirmed CODEOWNERS identities, and offline-safe backend CI.

## Status maintenance

For each row, update its state to one of `WAITING`, `HANDOFF READY`, `IN PROGRESS`, or `DONE — VERIFIED`. Add evidence before marking an item done. Keep the deferred work listed until the acceptance condition is met; never convert an unverified handoff into a completion claim.
