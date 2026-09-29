# Phase 7 — HARDIK / Rossonerian

## Decisions before implementation

- Supersede OD-3's v1 retention decision: freeze five synthetic CampusCart marketplace canaries at content_version v2. Keep SB-CAN-0001 through SB-CAN-0005 and their existing unique anchors so attack scripts require no modification. Content changes require new canonical SHA-256 hashes. Old datasets/replays are not valid final-run inputs.
- Brand the profile, inventory ledger, reconciliation API, handover rotation and cohort metric as CampusCart internal marketplace documentation. These are fictional trap claims, not facts about CampusCart.
- Retain OD-4's reverse-proxy strategy: /robots.txt advertises /internal/; a TRAPPED request to /internal/ receives all five paragraphs in edge-owned HTML with recorded exposures. The existing decoy API additionally delivers SB-CAN-0003. No CampusCart source changes or hydrated SPA injection. Existing /docs placements remain controlled local-fixture coverage only.
- Retain existing IDs, anchors and /internal/api/v3/quasar-reconcile URL. Freeze content, prompts, context terms, placements and hashes in a compact manifest without full content.
- Probe prompts must not contain any registered anchor or context term; ordinary subject vocabulary remains shared to support retrieval. Verify every probe retrieves its matching controlled-fixture paragraph.
- Reacquire public, unauthenticated CampusCart routes with the existing bounded Playwright control builder directly from https://campuscart-c73de.web.app, bypassing the edge. Preserve actual acquisition timestamps; live builds are not byte-deterministic.
- Reject empty hydration, edge honeypot markup, non-origin navigation, unsuccessful HTTP responses, and anchors anywhere in captured HTML/title/text. Check the committed JSONL and public baseline against all normalized registered anchors. Deterministic checks cover manifest hashing and repeated serialization of identical acquired records, not an assertion that live origin data never changes.
- Arnav must wait for this phase's merge before generating the final real scraper dataset. No provenance processing in this phase.

## Handoff

The compact manifest is data/canary_manifest.json. All five entries name /internal/ as the expected final scraper exposure surface; SB-CAN-0003 additionally names the decoy API. Full synthetic content stays in the registry and controlled sample fixture.

## Verification and freeze gate

- Direct-origin build: `/tmp/sb-venv/bin/python scripts/build_control_dataset.py` acquired 14 hydrated public routes, HTTP 200, zero registered anchors. Control SHA-256: `db149b52de047c9f635a2983166645cf37b3191770b3a57220bbf945086ba151`.
- `PYTHONPATH=backend /tmp/sb-venv/bin/python -m pytest backend/tests/unit backend/tests/contract backend/tests/integration scripts/tests -q -p no:cacheprovider`: 255 passed, 1 skipped, 2 subtests passed. Includes T-CA hashing/registry/uniqueness/prompt separation, frozen-manifest integrity and trap integration. Skip: optional real-botocore coverage without boto3.
- Runtime smoke with scratch SQLite: `/internal/` returned all five anchors, recorded all five session exposure links, and repeated rendering produced identical bytes.
- The initial v2 profile prompt retrieved a generic group-lead paragraph instead of the canary; the final principal-architect question passes top-1 retrieval. No xfail or answer-token leakage added.
- Live acquisition timestamps and changing upstream data prevent byte-identical live rebuild guarantees. Identical acquired-record serialization and repeated decoy rendering are stable; no real scraper or live LLM/provenance run was performed.
- Canary content is now frozen for the real scraper run. Arnav Phase 10 must reseed v2, generate a new real dataset after merge, and use this manifest and control; do not reuse v1 replay/target artifacts.

## Owner progress

OWNER: HARDIK / Rossonerian  
COMPLETED PHASES: 1 / 5  
REMAINING OWNER PHASES: 4 / 5

- P11 Real local provenance/evidence
- P12 S3 preservation implementation
- P14 S3 live acceptance
- P16 Provenance stability/replay

CURRENT HANDOFF: Frozen canary registry + clean control dataset → ARNAV Phase 10 real scraper dataset generation.
