# Phase 5 — Telemetry and Session Persistence Plan

## Inspection findings

The SQLite schema already defines `sessions`, `traffic_events`, `trap_hits`, and `exposures`. Session storage uses JSON columns for reasons, layer path, pages, traps, and canary IDs. Pipeline requests save a session in `finally`, but challenge verification saves separately, and trap hooks may update exposure data before the final session save. L3 trap hits are written to `trap_hits`; traffic decisions are written by the edge pipeline. The session and traffic APIs read SQLite. `/overview` aggregates decision counts and session classifications, but canary/case counts and trap/provenance stage health are placeholders.

## Persistence design

### Authoritative tables

- `sessions`: one row per stable `session_id`; authoritative current profile, state, classification, counters, scores/reasons, unique pages, layer history, trap IDs, and exposed canary IDs.
- `traffic_events`: append-only decision/event stream; authoritative per-request decision telemetry exposed by `/api/v1/traffic/events`.
- `trap_hits`: append-only L3 hit details, including trap identity/type/path; authoritative hit records produced by Hardik's trap classifier.
- `exposures`: append-only canary delivery records keyed to `session_id` and `canary_id`; authoritative exposure details produced by the existing canary registry.
- Existing `canaries` and `cases` tables remain the sources for overview counts; no contract or schema redesign is intended.

### Session write timing

1. Request entry initializes identity and fingerprint once, increments `request_count`, adds the path once, and updates `last_seen`.
2. Upsert the session as soon as request identity/counters are initialized and again at request completion, covering block, throttle, challenge, restricted, trap/decoy, and successful origin exits.
3. Challenge verification upserts the session after the L2 state/score/reason transition and counts the verification request.
4. Session reads and lists come only from SQLite. JSON arrays decode defensively and retain empty-list defaults.
5. Trap/exposure producers keep their existing table writes; the request-final session upsert captures the in-memory `traps_triggered` and `canaries_exposed` mutations.

### Event rule and vocabulary

Use one `traffic_events` row for each actual layer decision for a request, never a duplicate for the same layer/decision. Keep each row's `layer`/`decision` within the existing `TrafficEvent` literals:

- L1: `ALLOW`, `ESCALATE`, `CHALLENGE`, `THROTTLE`, `BLOCK`.
- L2: `CHALLENGE`, `PASS`, `TRAP`, `RESTRICT`.
- L3: `TRAP` for a matched trap.
- ORIGIN: `ALLOW` or `TRAP` for a completed origin/decoy delivery outcome, according to the current API contract's decision enum.

Do not invent new decision literals. Avoid recording `ESCALATE` twice when it causes an L2 challenge. Preserve distinct L1 and L2 rows when both layers make a decision. A trap hit is represented in `trap_hits` and one L3 `TRAP` traffic row; canary delivery is represented in `exposures` and the session's unique canary list.

### Exposure/trap relationships

- Every trap hit and exposure records the same stable `session_id` as the request's session row.
- L3 hit persistence is associated with the request context/session used by `layer3.classify_request`.
- A canary is added to `sessions.canaries_exposed` only when the producer confirms delivery, not when a placement is merely considered.
- Preserve Hardik's existing trap and exposure producer behavior and schema; capture their in-memory session mutations with the request-final upsert rather than creating competing exposure rows.

### API aggregation

- `/traffic/events` serializes persisted append-only rows and validates every returned row against the existing `TrafficEvent` contract.
- `/sessions` and `/sessions/{id}` serialize persisted session rows through the existing session store.
- `/overview` aggregates decision counts directly from `traffic_events`, class counts from `sessions`, canary active/exposed counts from `canaries`/`exposures`, and case totals/detected counts from `cases`. Optional/unavailable external services remain explicitly `null`/`unknown`; database-backed counts must not be fabricated.
- `/health` reports database availability from a real query and reports other component health only when a real probe/configured interface exists.

## Deterministic verification plan

1. Unit tests: session insert/update retains original `first_seen`, updates `last_seen`/counters, restores JSON fields, and handles trap/exposure lists.
2. Unit tests: event vocabulary validation and decision emission for allow, block, challenge, verify pass/restrict, trap, and origin; no duplicate escalation event.
3. Integration sequence: request → challenge → verify → origin or trap → canary exposure where applicable; assert persisted event count/order/vocabulary.
4. Compare `/api/v1/sessions/{id}` JSON to the matching database row after the sequence.
5. Verify trap hit and exposure rows reference the correct session; compare overview totals with direct SQL counts.
6. Deserialize every returned traffic event with the existing `TrafficEvent` model.

## Base branch

The user confirmed Phase 4 is merged. The local workspace cannot credential-fetch `origin/main`; its local ref is stale at `8238164`. This work branch was created from the available Phase 4 implementation commit `b1be396`, whose content includes Phase 4. Verify/rebase against the latest `main` before creating the PR if any later main commits exist.
