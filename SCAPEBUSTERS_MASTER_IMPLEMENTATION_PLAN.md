# SCAPEBUSTERS — Master Implementation Plan

**Version:** 2.0 (audited 2026-09-29) · **Event:** 30-hour hackathon · **Type:** proof-of-concept, one controlled demo target
**Rule:** ONE architecture · ONE master plan · ONE integration process · ONE deterministic demo.
This file is the single source of truth for the next agent prompts. Sections are referenced as `§N` (legacy spec) or `§I.x` (audited status, v2).

> **Canonical statement (operator, 2026-09-29):** CampusCart is the demo target. It is an external site, not a site built in this repo. This master plan supersedes the old ExampleCorp and `demo_site/` instructions. The CampusCart integration is on Arnav's branch `feat/arnav/campuscart-origin` (PR #8), **not** on current `main`. The dashboard is also absent from this repository.

## How to read this file

| Part | Contents | Authority |
|---|---|---|
| **Part I — v2 audited state** (`§I.A` … `§I.L`) | canonical direction changes, audited status, defects, CampusCart architecture, telemetry/dashboard flow, E2E, owner status, milestone reconciliation, remaining tasks, merge process, progress | **Wins on any conflict** |
| **Part II — legacy spec** (`§0` … `§27`) | the v1.0 target design (rules, thresholds, contracts, tests, task cards). Still the design intent for layers, canaries, provenance and evidence. Text tagged **[SUPERSEDED-v2]** is replaced by Part I | design intent; not a status source |
| **Part III** | `OPEN PR / MERGE QUEUE` and `NEXT AGENT GOALS` | current |

**Audit basis (evidence, not old plan claims):**

- Repository `https://github.com/BLITZKREIG-VOID/scrapebuster`, `main` at `4b1f0ea` ("Merge pull request #9 …"), audited 2026-09-29.
- All 9 remote branches and all `refs/pull/*/head` refs (#1–#10) fetched; PR merge state inferred from git ancestry.
- Tests executed by the auditor: `main` (unit, contract, integration), plus extracted snapshots of PR #8 and PR #10 heads. Results are in `§I.B.2`.
- **Not verifiable from the audit environment:** GitHub API (PR open/closed state, reviews, CI/check runs, base branches), the dashboard, live Ollama, AWS, Playwright/e2e runs. These are marked `NOT VERIFIED` and must not be treated as passing.

**Status vocabulary (use exactly these):**
`DONE — VERIFIED ON MAIN` · `IMPLEMENTED — OPEN PR` · `IMPLEMENTED — PENDING REVIEW` · `IMPLEMENTED — PENDING MERGE` · `PARTIAL` · `BLOCKED` · `NOT STARTED` · `NOT VERIFIED`.
A feature that exists only on a branch or PR is **not** done on `main`. Review status is separate from implementation status.

**Name mapping (per operator):** Arnav = `Kashyep` · Hardik = `Rossonerian` · Ani = `Anirudh-Langy`. Git author names observed in history: `Kashyep` / `Arnav Kashyap`; `Hardhik Bhatia`; `anigupta477-lang` / `Anirudh Gupta`. The GitHub-handle mapping could not be confirmed from the audit environment. The original plan's fourth owner, Harsh (dashboard), is not in the operator's owner list; see `§I.H`.

---

## I.A Canonical direction (v2) and source-of-truth rules

### I.A.1 Product-direction changes (canonical; replace conflicting assumptions)

| ID | Change | Replaces | Consequence |
|---|---|---|---|
| **C1** | **Real demo site.** The protected/demo target is the team's existing CampusCart deployment: `https://campuscart-c73de.web.app/`. It is an **external controlled demo target**; its source is **not** in this repository. | ExampleCorp origin, `demo_site/app.py`, `localhost:8001`, "build a new demo_site" | No `demo_site/` is built. Any task, test, script or doc that hard-codes ExampleCorp pages is stale unless it is an explicit local-test fixture. |
| **C2** | **All attack/security activity uses CampusCart.** Bot attacks and the ScrapeBuster layers operate only against CampusCart, through the ScrapeBuster edge. No scanning or attacking of third-party sites. Attacks are controlled, reproducible, volume-bounded, and must not disrupt normal users. | Generic/any-site targeting | Safe-demo rules `SD-1…SD-5` in `§I.C.3`. |
| **C3** | **Attack results feed the dashboard.** Security telemetry is a first-class pipeline: attack → request observed → session identified → layer decision → score/reasons → trap/challenge/block result → event persisted → API → dashboard. The final E2E must show **live persisted backend data**, not mock fixtures. | Dashboard on mock/invented data | Telemetry contract in `§I.D`; gaps listed in `§I.B.3`. |

### I.A.2 Source-of-truth rules

- **S1** `main` ≠ open PRs ≠ branches. Only `main` counts as done. Branch/PR-only work is `IMPLEMENTED — OPEN PR`.
- **S2** Never use a plan claim ("Layer 1 works") as evidence. Evidence = current `main` source, executed tests, `Makefile`, config, PR diffs.
- **S3** Part I overrides Part II. A Part II rule that conflicts with the implemented code is **not** silently accepted: it becomes an open decision (`§I.A.3`) that the owner must close in `docs/DECISIONS.md`.
- **S4** No secrets in the repository or this plan. AWS credentials, keys and account IDs are configured by the operator outside the repo.
- **S5** Every agent task ends with: what changed, how it was verified (actual command output), what was not verified.

### I.A.3 Open decisions (owner must close; do not build around silently)

| ID | Decision | Options | Recommendation | Owner |
|---|---|---|---|---|
| **OD-1** | Layer 1: code diverges from `§4` (see F-02). Conform code to `§4`, or amend `§4` to the implemented score-band design. | (a) conform: add THROTTLE/BLOCK, client_key windows, session block state; (b) amend `§4` and re-derive the ordinary-bot test | (a) minimally — the T-OB-1 gate and the demo narrative ("blocked at Layer 1") depend on it. Keep the table-driven structure. | Ani |
| **OD-2** | Layer 2: code diverges from `§5` (see F-03). | (a) conform: server-side signal scoring, PASS/TRAP/RESTRICT bands, `sb_clear` cookie; (b) amend `§5` | (a) — without RESTRICT and signals, Scraper 2 (headless Playwright) can solve the PoW and pass, so the L2 stage of the demo cannot occur. Endpoint paths may stay as implemented (`/_sb/challenge/verify`); amend `§5` paths instead of moving code. | Ani |
| **OD-3** | Canary branding on CampusCart. Canary text and decoy pages say "ExampleCorp / Nimbus…". | (a) keep the fictional ExampleCorp text; (b) re-theme to campus-marketplace context (`content_version` v2, new hashes, new prompts) | (b) if time allows before the first real dataset run; requires re-running T-CA-2/3 and stability. Team decision — the auditor did not decide. | Hardik + Arnav |
| **OD-4** | Canary surfaces on an SPA. CampusCart is a client-rendered Firebase SPA (per PR #8 site profile); the `/docs/*` placement pages of `§8` do not exist there and there is no `</main>` to inject into. | (a) canaries only via the trap decoys (PR #8 `_inject_all_canaries` on `/internal/`, plus decoy API); (b) additionally inject into hydrated pages | (a) for the POC; state it plainly in the pitch. | Hardik |
| **OD-5** | Edge integration method. | Reverse proxy at the demo laptop `localhost:8000` → `UPSTREAM_ORIGIN` (implemented in PR #8). DNS/CDN-level fronting is **not** implemented and not required. | Use the reverse proxy. Do not invent another deployment. | Ani |
| **OD-6** | Dashboard: no `dashboard/` exists on any ref of this repo. Where does it live and who owns it? | in-repo `dashboard/` (per `§14`) or separate repo | Operator to state. Until then `dashboard` rows are `NOT VERIFIED`. | Operator |
| **OD-7** | Is AWS usage judged? If yes, promote S3 Object Lock from P1-high to P0 (still with local fallback). | yes / no | Operator to state. | Operator |

---

## I.B CURRENT IMPLEMENTATION STATUS — AUDIT 2026-09-29

### I.B.1 Repository state

| Item | Value |
|---|---|
| `main` HEAD | `4b1f0ea` (PR #9 merge) |
| Tag | `contracts-v1` → `45e5f7c` (ancestor of `main`) |
| Files on `main` | 131 tracked; `dashboard/` and `demo_site/` exist on **no** ref |
| Merged into `main` (head is ancestor) | PR #1, #2, #3, #4, #5, #6, #9 |
| Not in `main` | PR #7 (`e330db1`), PR #8 (`b1ea3b0`), PR #10 (`7c2ff52`; head moved from `ffacc3b` during the audit) |
| Merge conflicts with `main` | none for #7, #8, #10 (`git merge-tree --write-tree`) |
| Root-level legacy files | `index.js`, `src/`, `package.json`, `README.md` describe an unrelated Node scraper (stale; adjacent issue, not part of this plan) |

### I.B.2 Test evidence (executed by the auditor, 2026-09-29)

Command form: `PYTHONPATH=backend SB_DB_PATH=<scratch> python3 -m pytest <dir> -q` (Python 3.11.15; deps installed from `backend/requirements*.txt`; PyYAML/playwright were already present in the audit environment).

| Ref | unit | contract | integration | Notes |
|---|---|---|---|---|
| `main` | 139 passed, 2 skipped, 1 xfailed | 4 passed | 5 passed, 1 xfailed | skips: `test_uniqueness.py` (no `demo_site/pages`, no control dataset); xfail: `SB-CAN-0004` prompt overlap; xfail: `test_l1_ordinary_bot` — "missing dependency: sb.main:demo_router" |
| PR #8 head | 150 passed, 2 skipped, 2 xfailed across unit+contract+integration | | | same skips/xfails |
| PR #10 head | 154 passed, 3 skipped, 2 xfailed across unit+contract+integration | | | extra skip: real-botocore test (`boto3` not installed) |

Other gates on `main`: `ruff check backend/ scripts attacks` → **12 errors** (E402 in test `conftest.py` files and `scripts/stability.py`); `scripts/check_contracts.py` → "No JSON fixtures found to validate." (vacuous pass); `scripts/check_ownership.py` → passed (no changed files).
**e2e (`backend/tests/e2e`) was not executed**: it needs Playwright browsers, a reachable upstream and the demo router; every scenario is `xfail(strict)`-gated on missing modules.
Measured Layer 1 behaviour (auditor script calling `layer1.run` with default `python-requests` headers, 100 requests): 39× ESCALATE (proxied to origin), 61× CHALLENGE, max score 75, **no BLOCK**.
Reachability only: one `GET https://campuscart-c73de.web.app/` from the audit workspace returned HTTP 200 `text/html`. No attack was run against it.

### I.B.3 Defect and gap register (verified against source; each has an owner)

| ID | Finding | Evidence | Owner |
|---|---|---|---|
| **F-01** | **Provenance and demo APIs are not mounted.** `sb/main.py` includes only health, traffic, sessions, overview. `canaries`, `datasets`, `probes`, `cases` (Hardik) and `demo` (Arnav) routers exist but are never included, so their URLs fall through to the catch-all proxy. The dashboard cannot read canaries/probes/cases/evidence, and the e2e/runner cannot start. | `backend/sb/main.py:24-29`; `api/demo.py` docstring "Mount in sb/main.py"; xfail reason in `test_l1_ordinary_bot` | Ani |
| **F-02** | **Layer 1 ≠ spec §4 and cannot stop the ordinary bot.** Implemented: score bands ALLOW/ESCALATE/CHALLENGE/BLOCK, per-IP 60 s window (40/80/150), block only at score ≥ 90. Missing vs `§4`: THROTTLE, `client_key` windows, HTTP-fingerprint rule, `L1_*` reason codes, session BLOCKED state and expiry (`Session.block_expired()` always `False`; pipeline never checks `state == BLOCKED`). Measured: a 100-request python-requests burst never reaches BLOCK, and the first 39 requests are ESCALATE, which the pipeline proxies to the origin. T-OB-1 ("0 origin pages") cannot pass. | `edge/layer1.py`, `edge/session.py`, `edge/pipeline.py:90-95`, auditor run in `§I.B.2` | Ani |
| **F-03** | **Layer 2 ≠ spec §5.** Implemented: hex-prefix PoW (`"000"`) only, served only when L1 lands in CHALLENGE (403 page). No server-side signal scoring (verify takes only `challenge_id` + `solution`; `challenge.js` builds a `signals` object the server ignores), no PASS/TRAP/RESTRICT bands, no RESTRICT state/decision, no `sb_clear` cookie (clearance = in-memory `session.state == "VERIFIED"`). Endpoints differ (`/_sb/challenge/verify`, `/_sb/static/challenge.js`). The interstitial says "Security Check", but attacks look for `INTERSTITIAL_MARKER = "Checking your browser"`. A headless browser that runs JS solves this PoW. | `edge/layer2.py`, `main.py:31-59`, `attacks/common.py:21`, `docs/api/INT-07-Layer-2.md` | Ani |
| **F-04** | **Telemetry incomplete (C3).** (a) Only `layer="L1"` rows are written; no L2 issue/verify/restrict rows, no L3 `TRAP` row (trap decisions exist only in in-memory `layer_path`). (b) Decision `CHALLENGE_BYPASSED` is not in the `TrafficEvent` literal; `GET /traffic/events` would raise a validation error once such a row exists (reproduced with pydantic). (c) ESCALATE is logged twice (pre-proxy status 0, post-proxy). (d) The `sessions` table is never written; sessions live only in memory. (e) `GET /sessions/{id}` returns hard-coded `ip=127.0.0.1` and empty `user_agent`, `header_fp`, `first_seen`, `last_seen`, `l1_reasons`, `l2_signals`, `pages`, `traps_triggered`, `canaries_exposed`; `request_count = len(layer_path)`. (f) `_note_exposure` updates a `sessions` row that never exists. (g) `/overview` hard-codes `canaries`, `cases`, `ladder.provenance`, `pipeline`. (h) `/health` returns only `{"status":"ok"}`; no `db/origin/llm/s3` components. | `edge/pipeline.py:27-56,78-115`; `api/sessions.py`; `api/overview.py`; `api/health.py`; `contracts.py` | Ani |
| **F-05** | **CampusCart integration is unmerged.** On `main`, the origin defaults to `http://127.0.0.1:8001` (no such site exists on any ref); attacks default to ExampleCorp pages. PR #8 adds `UPSTREAM_ORIGIN` (default the CampusCart URL), Host rewrite, identity `Accept-Encoding`, edge-owned `robots.txt` (`Disallow: /internal/`), robots-trap injection of all canaries, CampusCart site profile in `attacks/common.py`, preflight/smoke updates. PR #8 also edits files owned by others (`sb/trap/injector.py` Hardik; `sb/edge/proxy.py`, `sb/config.py` Ani) — needs their review. | `git diff origin/main...pr/8` | Arnav (+ Ani, Hardik review) |
| **F-06** | **No control dataset and no real dataset.** `data/control/control_clean.jsonl` does not exist (its builder reads the non-existent `demo_site/pages`); runner step 4 needs it; T-CA-2 is skipped. `data/replay/replay_20260929T101520Z.json` was captured from the sample fixture stand-in (commit `3bc04b9`), not from a CampusCart scrape. No stability numbers are logged (`docs/INTEGRATION_LOG.md` is empty). | `scripts/build_control_dataset.py`; skips in `test_uniqueness.py`; `docs/INTEGRATION_LOG.md` | Hardik |
| **F-07** | **Makefile is incomplete.** `.PHONY` lists `e2e preflight demo demo-step capture-golden restore-golden smoke` but no recipes exist; `site` runs `demo_site.app` (absent); `setup`/`dashboard`/`check` call into `dashboard/` (absent); `up` is a placeholder; `reset` only calls `reset_db()` (not the §21 demo reset). `make check` cannot pass. | `Makefile` | Ani (base) / Arnav (demo targets) |
| **F-08** | **No CI for tests.** The only workflow is `jules-pr-review.yml` (AI review). Nothing runs ruff/pytest/contracts on PRs. 12 ruff errors persist on `main`. | `.github/workflows/`, ruff run | Ani |
| **F-09** | **Requirements incomplete.** `backend/requirements.txt` lacks `PyYAML` (canary registry imports `yaml`), `boto3` (vault, PR #7/#10), `requests` and `playwright` (attacks). Clean-venv install not verified. | `requirements*.txt`, imports | Ani |
| **F-10** | **Contract fixtures absent.** `contracts/fixtures/` holds only `scraped_dataset_sample.jsonl`; there are no JSON fixtures, so the drift gate is vacuous and dashboard mock mode has nothing to read. `contracts.py` lacks models for Overview, Probe/Evidence/Verify responses (defined ad hoc inside `api/*.py`), and `Health.components`. | `contracts/`, `contracts.py` | Ani (+ Hardik for provenance models) |
| **F-11** | **Ownership metadata stale.** `CODEOWNERS` uses placeholder handles (`@anirudh`, `@hardik`, `@arnav`, `@harsh`) and legacy paths (`/demo_site/`, `/tests/e2e/`); `.gitignore` does not list `evidence/`, `data/datasets/`, `data/golden/`. | `.github/CODEOWNERS`, `.gitignore` | Ani |
| **F-12** | **S3 is a stub on `main`.** `vault_s3.py` only has `s3_status()` and can never report "ok". Upload (PRV-08) exists only in PR #7/#10. | `provenance/vault_s3.py` on `main` vs `pr/10` | Hardik |

### I.B.4 Status table

| Area | Owner | Main | PR | Status | Evidence | Remaining |
|---|---|---|---|---|---|---|
| contracts | Ani | `contracts.py`, 11 JSON schemas, tag `contracts-v1` | — | PARTIAL | `make test-contract` 4 passed; `check_contracts.py` "No JSON fixtures found" (F-10) | add response models + JSON fixtures; `Health.components`; telemetry fields |
| backend bootstrap | Ani | app, store (`schema.sql`, `db.py`), proxy, pipeline, config | #8 (config/proxy) | PARTIAL | `main.py` mounts 4 routers (F-01); Makefile gaps (F-07); requirements (F-09) | mount all routers; requirements; Makefile base targets |
| Layer 1 | Ani | `edge/layer1.py` (INT-06) | — | PARTIAL (non-conformant) | `test_layer1.py` passes but measured burst never blocks (F-02) | close OD-1; implement chosen design; unxfail T-OB-1 |
| Layer 2 | Ani | `edge/layer2.py`, `static/challenge.js` (INT-07) | — | PARTIAL (non-conformant) | `test_layer2.py` + `test_layer2_flow.py` pass for the PoW-only design (F-03) | close OD-2; signals, bands, RESTRICT, clearance cookie; align interstitial marker |
| Layer 3 | Hardik (hooks in pipeline: Ani) | `trap/` (`layer3`, `honeypots`, `decoys`, `injector`), hooks registered at startup | #8 (robots lure, inject-all) | PARTIAL | trap unit + `test_trap_injection` pass; no `TRAP` traffic row (F-04a) | log L3 events; CampusCart robots lure via #8; unit-test the #8 path on merge |
| traps | Hardik | `TRAP-LINK-01`, `TRAP-ROBOTS-01`, `TRAP-DECOY-01`, `TRAP-BAND-L2` in code | #8 | PARTIAL | `trap_hits` written by `layer3.classify_request`; decoy pages branded "ExampleCorp" (OD-3) | OD-3/OD-4; edge `robots.txt` only in #8 |
| canaries | Hardik | `canary/` (yaml, hashing, registry, seed) | — | DONE — VERIFIED ON MAIN (unit); NOT VERIFIED on CampusCart | canary unit tests pass; T-CA-2 skipped | OD-3 branding; T-CA-2 against CampusCart content |
| dataset ingestion | Hardik | `provenance/dataset.py`, `api/datasets.py` (unmounted) | — | PARTIAL | dataset unit tests pass; route unreachable (F-01); no real dataset ingested | mount; ingest CampusCart scrape + control |
| RAG | Hardik | `provenance/rag.py` | — | DONE — VERIFIED ON MAIN (unit) | `test_rag.py` passes; `SB-CAN-0004` xfail (prompt lexical overlap) | close the `SB-CAN-0004` prompt decision (OD-3) |
| Doberman | Hardik | `provenance/doberman.py`, `llm.py` | — | PARTIAL | unit tests pass with LLM stubbed; live Ollama not verified by auditor | live run on real dataset; record model mode/digest |
| correlation | Hardik | `provenance/correlate.py` | — | DONE — VERIFIED ON MAIN (unit) | `test_correlate.py` passes (positive, clean-control negative, ordering/integrity) | none until real-data run |
| evidence | Hardik | `provenance/evidence.py`, `investigate.py`, `api/cases.py` (unmounted) | — | DONE — VERIFIED ON MAIN (module: T-EV-1/2); API unreachable | `test_evidence.py` incl. tamper, chain, self-hash | mount cases router (F-01) |
| S3 | Hardik | status stub only (F-12) | #7, #10 | IMPLEMENTED — OPEN PR (PR #10 stacks on #7) | PR #10 snapshot: 154 passed, real-botocore test skipped (no boto3); no AWS run | merge #7 then #10; add `boto3`; operator AWS config; acceptance via `get-object-retention` |
| attack scripts | Arnav | `attacks/` 4 scripts + `common.py` (default ExampleCorp pages) | #8 (CampusCart profile) | PARTIAL | present on `main`; not executed by auditor | verify each against CampusCart via the edge after #8 + fixes |
| CampusCart integration | Arnav (proxy: Ani) | not on `main` | #8 | IMPLEMENTED — OPEN PR | diff read; snapshot tests 150 passed; root URL HTTP 200 (reachability only) | review, merge, real run; safe-mode guard (SD-1…5) |
| attack telemetry | Ani | L1 rows in `traffic_events` only | — | PARTIAL | F-04 | L2/L3 rows, contract-legal decisions, persisted sessions |
| dashboard | not in repo (OD-6) | none | none | NOT STARTED in this repo / NOT VERIFIED elsewhere | no `dashboard/` on any ref | operator to state location/owner |
| dashboard live API integration | Ani + Hardik | 5 of 20 endpoints reachable (health, overview, traffic/events, sessions, sessions/{id}) | — | PARTIAL | F-01, F-04 | mount, real aggregation, fixtures |
| E2E runner | Arnav | `demo/runner.py`, `api/demo.py`, e2e tests | — | BLOCKED | routers unmounted; upstream/control/ExampleCorp constants (`tests/e2e/conftest.py` BRAND/ORIGIN_PAGES) | unblock (F-01), retarget tests to CampusCart, run |
| reset | Arnav | `demo/reset.py` (§21 steps) | #8 (origin URL) | BLOCKED | needs mounted `/demo/reset`, `seed_canaries`; not executed | run T-RS-1 |
| golden/replay | Arnav / Hardik | `demo/golden.py`; `data/replay/…json` (fixture stand-in) | — | NOT VERIFIED | `data/golden/` absent; replay not from CampusCart | capture golden from first real pass; new replay from real dataset |
| CI | Ani | Jules AI review workflow only | — | NOT STARTED (test CI) | `.github/workflows/` | P1: workflow running ruff + pytest + contracts |
| integration gates | Ani | `check_ownership.py`, `check_contracts.py`, PR template, CODEOWNERS | — | PARTIAL | placeholder handles, vacuous contract gate (F-10, F-11) | real fixtures; real handles |
| reliability (M10) | Arnav | — | — | NOT STARTED | — | 3 consecutive live passes |
| final demo (M11) | all | — | — | NOT STARTED | — | rehearsals + failure drill |

---

## I.C Target architecture and runtime flow (CampusCart)

### I.C.1 Diagram

```text
                      CAMPUSCART  (external, team-owned, controlled demo target)
                      https://campuscart-c73de.web.app/   -- source NOT in this repo
                                        ▲
                                        │ httpx, Host rewritten to the target host, Accept-Encoding: identity
   human / bots ──►  SCAPEBUSTERS EDGE  (FastAPI, laptop :8000, backend/sb)
   (only ever aimed   context → session → L1 → L2 → L3 hooks → proxy → transform_response
    at the edge)      /robots.txt served by the edge (Disallow: /internal/)          [PR #8]
                      exempt: /api/*, /_sb/*, /static/*, /health, /favicon.ico
                                        │ persisted events: traffic_events, trap_hits, exposures (SQLite)
                                        ▼
   scraper 3 ─► data/datasets/<run>_scraper3.jsonl ─► ingest (target) + control ─► RAG + Ollama ─► Doberman
                                        ▼                                            ─► correlation ─► evidence bundle
                                CONTROL API /api/v1/*  ─────────────────────────────► S3 Object Lock (if configured)
                                        ▼
                                DASHBOARD (reads only this API; live mode for the final E2E)
```

**Integration method (as implemented, not invented):** the edge is a reverse proxy in front of `UPSTREAM_ORIGIN` (PR #8; falls back to `SB_ORIGIN_URL`; PR #8 default is the CampusCart URL). Attack scripts and the browser under test connect to the **edge** (`SB_EDGE_URL`, default `http://127.0.0.1:8000`), never directly to CampusCart. The CampusCart deployment itself is not modified.

### I.C.2 Runtime request flow

The decision flow of `§3` remains the design intent. Implemented flow today: `context → session → intel.init_request → L1 (bands) → [BLOCK 403 | CHALLENGE → L2 page 403 | ESCALATE → state SUSPICIOUS, continue] → trap_hooks.classify_request (TRAP → mark_trapped → handle_decoy) → proxy → trap_hooks.transform_response → log`. Deviations that break the demo narrative are F-02, F-03, F-04. **Target for v2:** every branch writes exactly one contract-legal `traffic_events` row (`§I.D`) and updates a persisted session.

### I.C.3 Safe demo mode (C2)

| ID | Rule | Status |
|---|---|---|
| SD-1 | Attack scripts accept only the edge as `--base` (default `http://localhost:8000`); refuse non-loopback bases unless an explicit override flag is passed | NOT STARTED (defaults are safe today; no guard) — Arnav |
| SD-2 | Fixed request budgets (ordinary bot default 100 requests / 10 threads; crawler bounded by page list and 2–3 s delay) documented and capped per run | PARTIAL (defaults exist in scripts) — Arnav |
| SD-3 | Blocked/challenged traffic never reaches CampusCart: L1/L2 decisions occur before `proxy()`; F-02 currently violates this for ESCALATE | BLOCKED on F-02 — Ani |
| SD-4 | Demo runs use a marked test client (dedicated User-Agent suffix per attack script) so real CampusCart visitors are never classified, trapped or exposed to canaries; canaries and decoys are served only to TRAPPED demo sessions | PARTIAL (injector serves canaries only to TRAPPED sessions; UA marking NOT STARTED) — Arnav/Hardik |
| SD-5 | The edge forwards only to the configured upstream; no request-controlled upstream host | DONE — VERIFIED ON MAIN by source (`proxy.py` uses `SB_ORIGIN_URL` only) |

---

## I.D Telemetry pipeline and dashboard data flow (C3)

```text
attack ─► request observed (context) ─► session identified (persisted)
       ─► layer decision (L1/L2/L3) + score + reasons ─► trap / challenge / block result
       ─► event persisted (traffic_events, sessions, trap_hits, exposures)
       ─► Control API ─► Dashboard
```

### I.D.1 Required fields and where they must come from

| Dashboard field | Source of truth | Today |
|---|---|---|
| timestamp | `traffic_events.ts` | OK (L1 rows only) |
| session/client | `traffic_events.session_id/client_key/ip/user_agent` + persisted `sessions` row | events OK; sessions row never written (F-04d) |
| path | `traffic_events.path` | OK |
| layer | `traffic_events.layer` ∈ L1/L2/L3/ORIGIN | only L1 written (F-04a) |
| decision | `traffic_events.decision` (contract literal only) | `CHALLENGE_BYPASSED` illegal (F-04b) |
| score | `traffic_events.risk_score` | L1 score only |
| reasons | `traffic_events.reasons` | L1 reasons only |
| classification | `sessions.classification` (recomputed on each decision) | in-memory only |
| state transition | `sessions.layer_path` and/or state-change events | in-memory only |
| trap hit | `trap_hits` + an L3 `TRAP` traffic row | `trap_hits` written; traffic row missing |
| canary exposure | `exposures` (+ `sessions.canaries_exposed`) | `exposures` written; session link broken (F-04f) |
| provenance case/evidence link | `cases.session_ids`, `cases.findings`, `evidence_objects` | written by provenance; not exposed until routers mounted |

### I.D.2 Endpoint map (what populates each dashboard view)

| View | Endpoints (all `GET` unless noted) | Reachable on `main` | Data persisted? |
|---|---|---|---|
| **Overview** | `/api/v1/health`, `/api/v1/overview`, `/api/v1/demo/status` | health (status only), overview (partly hard-coded), demo unreachable | traffic counts from SQLite; canaries/cases/pipeline hard-coded |
| **Traffic / Scrapers** | `/api/v1/traffic/events?after=`, `/api/v1/sessions`, `/api/v1/sessions/{id}` | yes | events persisted (L1 only); sessions in memory with stubbed detail |
| **Canaries** | `/api/v1/canaries`, `/api/v1/canaries/{id}` | no (router unmounted) | `canaries`, `publications`, `exposures` persisted |
| **Probes** | `/api/v1/datasets`, `POST /api/v1/datasets/ingest`, `/api/v1/probes`, `/api/v1/probes/{id}`, `POST /api/v1/probes/run` | no | `datasets`, `probe_runs`, `probe_results` persisted |
| **Cases** | `/api/v1/cases`, `/api/v1/cases/{id}` | no | `cases` persisted |
| **Evidence** | `/api/v1/cases/{id}/evidence`, `POST /api/v1/cases/{id}/verify` (receipt/S3 status included in evidence response; `s3` component in `/health`) | no | `evidence_objects` + bundle on disk |
| Demo panel | `POST /api/v1/demo/reset`, `POST /api/v1/demo/run`, `GET /api/v1/demo/status`, `POST /api/v1/demo/restore-golden` | no | `demo_state` |

### I.D.3 Live-data rule

- Mock mode (`VITE_API_MODE=mock`, reading `contracts/fixtures/*.json`) is allowed for frontend development only.
- The final E2E (`§I.E`, M9) and every rehearsal run in **live** mode. Acceptance check: record counts shown on each dashboard view equal the counts returned by the API/DB for the same run; no view may fall back to a fixture.
- Contract tests validate **live** responses against `contracts.py` for every GET above (T-DB-2).

---

## I.E E2E demo definition (target: CampusCart)

Runner reality: `demo/runner.py` implements 7 machine steps (`ordinary_bot`, `advanced_scraper`, `sophisticated_scraper`, `ingest_datasets`, `probe`, `case_check`, `verify_evidence`), plus reset. The 15 conceptual steps below are the acceptance definition; the mapping is in the last column.

| # | Step | Owner | API / data dependency | PASS condition | FAIL condition | Fallback | Runner step |
|---|---|---|---|---|---|---|---|
| 1 | Reset | Arnav | `POST /demo/reset` (F-01) | `ok:true`; §21 tables empty; 5 ACTIVE canaries; upstream reachable | any check `ok:false`; 409 | re-run once; else `make up && make reset` | reset |
| 2 | Human/control interaction with CampusCart | Arnav | `attacks/human_control.py`, `/sessions` | ≥ 5 CampusCart pages served; classification `HUMAN_LIKELY`; **0 exposures** | any canary or trap served to it; non-200 | manual fresh Incognito browse | (pre-step) |
| 3 | Ordinary bot attacks CampusCart | Arnav (L1: Ani) | `ordinary_bot.py`, `/traffic/events`, `/sessions` | session `BOT_BASIC`, state BLOCKED within the request budget; **0 CampusCart content in any bot response** | any origin content reaches the bot (F-02 today) | none (fix F-02) | 1 |
| 4 | Security layer logs and classifies traffic | Ani | `traffic_events`, `sessions` (persisted) | every request of steps 2–3 has one legal row with layer, decision, score, reasons; session persisted with classification | missing/illegal row; `/traffic/events` error | none | (cross-cuts 1–3) |
| 5 | Advanced automation escalated/restricted | Arnav (L2: Ani) | `advanced_scraper.py`, `/sessions`, L2 rows | session `AUTOMATION`, state RESTRICTED; L2 CHALLENGE/RESTRICT rows with signal reasons; no content served | passes L2 (F-03 today) | `POST /demo/restore-golden` (labelled `RECORDED RUN`) | 2 |
| 6 | Sophisticated scraper is trapped | Arnav / Hardik | `sophisticated_scraper.py`, `trap_hits`, L3 rows | L2 PASS row then `TRAP` row; `TRAP-ROBOTS-01` (or link/decoy) hit; class `SOPHISTICATED_SCRAPER` | never trapped | retry once; else restore golden | 3 |
| 7 | Canary exposure recorded | Hardik | `exposures`, `/canaries/{id}` | exposures for all 5 canaries linked to the session; canary status EXPOSED | < 5 exposures or no session link | none | 3 |
| 8 | Scraped dataset generated from CampusCart | Arnav | `data/datasets/<run>_scraper3.jsonl` | file exists; records include the 5 canary anchors | missing/empty; anchors absent | restore golden | 3 |
| 9 | Target + control datasets ingested | Hardik / Arnav | `POST /datasets/ingest` ×2 | 2 datasets registered; control contains 0 anchors; control built from CampusCart content without the edge | control missing (F-06); anchor in control | none | 4 |
| 10 | Doberman probes target and control | Hardik | `POST /probes/run`, `/probes/{id}` | both runs `DONE`; model mode/digest shown (LIVE / FALLBACK / REPLAY) | run fails/timeouts | extractive fallback (badge FALLBACK); else restore golden | 5 |
| 11 | Correlation identifies provenance signal | Hardik | `/cases` | latest case `PROVENANCE_SIGNAL_DETECTED`; control negative | status ≠ detected; control positive | restore golden | 6 |
| 12 | Evidence bundle generated | Hardik | `/cases/{id}/evidence` | manifest + files present, chain link to previous manifest | missing files | none | 6 |
| 13 | Evidence verified | Hardik | `POST /cases/{id}/verify` | `VALID` | `TAMPERED` | none | 7 |
| 14 | AWS/S3 preservation (if enabled) | Hardik (operator configures AWS) | `/health` s3, evidence `receipt` | receipt with `VersionId` + retain-until; else honest `disabled`/`PRESERVED_LOCAL` | `down` when enabled | local-only label | (part of 6) |
| 15 | Dashboard displays the complete incident | Ani (+ dashboard owner, OD-6) | all `§I.D.2` endpoints, **live mode** | every view populated from live API; counts equal API/DB; case + evidence view shows the finding and statement `§11.4` | any view empty/mock; API-unreachable banner | manual refresh; backup video | (observed) |

**Wording rule (all steps and pitch):** a canary in model output is a *provenance signal* / *evidence of exposure*, not proof of theft, intent or legal causation (§11.4 statement is mandatory in every case).

---

## I.F Reset and recovery (CampusCart)

- `§21` reset order stands. CampusCart is external: **nothing on the target is reset**; only ScrapeBuster state (DB, edge sessions, challenges, trap/provenance caches, runtime datasets) is cleared. Evidence is never deleted.
- Self-check upstream reachability = `GET UPSTREAM_ORIGIN/` returns 200 with the CampusCart marker (`<title>campuscart</title>`, as coded in PR #8 `preflight.py`).
- Added failure rows: **CampusCart unreachable** → do not attack anything else; run from the golden run and the backup video, label `RECORDED RUN`. **Upstream rate/limit signals** (429/5xx) → stop the attack step, lower request budget (SD-2), do not retry in a loop.
- Golden run is captured only after the first fully passing **live** run against CampusCart (never from the fixture stand-in).

---

## I.G AWS role (v2)

| Item | Owner | Status |
|---|---|---|
| AWS account, profile, region, S3 bucket with Object Lock enabled, credentials via the standard AWS credential chain (never in the repo) | **Operator (user)** — not assigned to Arnav/Hardik/Ani | operator |
| S3 upload code (GOVERNANCE, 24 h, SHA256, background, single attempt, receipt) | Hardik | IMPLEMENTED — OPEN PR (#7, #10) |
| Runtime wiring: read `SB_S3_BUCKET` / `AWS_REGION` from config, `boto3` in requirements, `Health.components.s3` | Ani | NOT STARTED |
| Dashboard consumption | dashboard owner | reads S3 receipt from `/cases/{id}/evidence` and status from `/health` |
| DynamoDB mirror, SNS alert | — | **optional** (P1-low). Not required by any current code path; do not build unless OD-7 says AWS is judged and M9 is green |
| S3 Object Lock as P0 | — | depends on OD-7; local hash-chained evidence remains the primary preservation path and the demo never depends on AWS |

No QLDB (support ended). Wording: S3 Object Lock = WORM retention; not a blockchain, not court-equivalent.

---

## I.H OWNER STATUS

### ARNAV — Kashyep

**DONE (present on `main`; runtime behaviour not executed by the auditor)**

- `attacks/` scripts `ordinary_bot`, `advanced_scraper`, `sophisticated_scraper`, `human_control`, `common` (PR #2).
- `sb/demo/` `reset`, `runner`, `golden`; `api/demo.py`; `scripts/preflight.py`, `scripts/smoke.sh`; e2e harness and scenario tests (PR #2).
- Ruff fixes (PR #6); Jules review timeout fix (PR #9).

**IMPLEMENTED BUT NOT MERGED**

- PR #8 `feat/arnav/campuscart-origin`: attacks retargeted to CampusCart (site profile, `UPSTREAM_ORIGIN`), Host rewrite/identity encoding, edge `robots.txt` lure, `TRAP-ROBOTS-01` inject-all-canaries, preflight/smoke for CampusCart. Snapshot tests: 150 passed, 2 skipped, 2 xfailed. Review/CI status NOT VERIFIED.

**LEFT**

1. Get PR #8 reviewed and merged (Ani reviews `proxy.py`/`config.py`; Hardik reviews `injector.py`).
2. Retarget `backend/tests/e2e/conftest.py` (`BRAND`, `ORIGIN_PAGES`, `ORIGIN`) and layer-validation tests to the CampusCart site profile; keep ExampleCorp only as an explicit local fixture.
3. Makefile demo targets: `e2e`, `preflight`, `demo`, `demo-step`, `capture-golden`, `restore-golden`, `smoke` (currently `.PHONY` with no recipes, F-07); `make reset` → §21 demo reset.
4. Safe-mode guard SD-1/SD-2/SD-4 in `attacks/` (loopback-only base, request caps, marked test UA).
5. After the blockers below clear: real runs of scripts 1–3 + human control against CampusCart via the edge; verify T-OB-1, T-AS-1, T-SS-1, T-NU-1 unxfailed; then T-E2E-1, T-RS-1, T-RS-2 (3 consecutive), golden capture, backup video.

**BLOCKERS**

- Ani: mount `demo` router (F-01); L1/L2 conformance (F-02/F-03); L2/L3 telemetry (F-04).
- Hardik: CampusCart control dataset (F-06); canary branding decision (OD-3).
- PR #8 merge.

**FINISH CONDITION** — `make preflight` has no FAIL; `make reset` → 5 ACTIVE canaries, zero traffic, new `run_id`; `make demo` passes steps 1–7 **live** against CampusCart; T-E2E-1, T-RS-1 pass; three consecutive `make reset && make demo` passes are logged in `docs/INTEGRATION_LOG.md`; golden restore and backup video verified.

### HARDIK — Rossonerian

**DONE (on `main`, verified by executed unit/integration tests)**

- Canaries: `canaries.yaml`, hashing, registry, seed (T-CA-1).
- Layer 3: honeypots, decoys, injector, `TrapHooks` installed at startup (PR #3, #4); `test_trap_injection` passes.
- Provenance: dataset ingest, BM25 RAG, LLM client (fallback + replay), Doberman, correlation (incl. clean-control negative), evidence bundle/chain/verify (T-EV-1/2), investigate pipeline; provenance API routers (files only — unmounted, F-01); `scripts/stability.py`; replay file (fixture stand-in).
- Jules review workflow (`55569a5`).

**IMPLEMENTED BUT NOT MERGED**

- PR #7 `feat/hardik/s3-vault` (PRV-08 S3 Object Lock vault: GOVERNANCE 24 h, SHA256, background upload, receipt).
- PR #10 `fix/vault-s3-receipt-db-failure` (stacked on #7: receipt/DB-failure handling, single-attempt retry config). Snapshot: 154 passed, 3 skipped; real-botocore test skipped here (no `boto3`); no AWS run. Review/CI NOT VERIFIED.

**LEFT** (only what is unresolved)

1. Close OD-3/OD-4 (canary branding and surfaces on the CampusCart SPA); resolve the `SB-CAN-0004` prompt xfail; update `canaries.yaml`, decoys and probe prompts if re-themed (new `content_version`, re-run T-CA-2/T-CA-3).
2. CampusCart control dataset: rewrite `scripts/build_control_dataset.py` to build `data/control/control_clean.jsonl` from CampusCart content fetched **without** the edge; enable T-CA-2 against it (F-06).
3. Real scraped dataset: ingest the scraper-3 output via `POST /datasets/ingest`; live Doberman run against it; PRV-07 stability (10 runs) on the real dataset with numbers recorded in `docs/INTEGRATION_LOG.md`; new replay capture from real data.
4. S3: after #7/#10 merge and operator AWS setup, acceptance via `aws s3api get-object-retention` (GOVERNANCE + date); AWS unset → `PRESERVED_LOCAL`, no exception.
5. Provenance→dashboard dependencies: with Ani, expose canary/exposure counts to `/overview`, move ad hoc response models into `contracts.py`, and make case `session_ids` link to real persisted sessions.

**BLOCKERS** — Ani: router mount (F-01), persisted sessions (F-04d); Arnav: PR #8 merge and a real scraper-3 dataset; operator: AWS configuration and OD-7.

**FINISH CONDITION** — On a real CampusCart scrape: target run yields case `PROVENANCE_SIGNAL_DETECTED` with statement §11.4, control yields NO_SIGNAL for all canaries, `verify` returns VALID, tamper test returns TAMPERED; stability ≥ 9/10 per canary (flaky canaries removed via `SB_PROBE_CANARIES`); S3 receipt present when AWS is configured (otherwise honest `disabled`).

### ANI — Anirudh-Langy

**DONE (on `main`)**

- Repo bootstrap, `contracts-v1` tag, store/schema (`45e5f7c`); INT-05 control API health/traffic/sessions/overview (PR #1); edge pipeline skeleton; Layer 1 (`abb0f89`), Layer 2 (`f484339`), intel/classification (`ddb67a1`) — implemented, unit-tested, but **PARTIAL vs spec** (F-02/F-03); integration gates `check_ownership.py`/`check_contracts.py`/PR template/CODEOWNERS (`d08289e`, PARTIAL — F-10/F-11).

**IMPLEMENTED BUT NOT MERGED** — none identified (no open Ani-authored branch; `feat/anirudh/int-05-control-api` is merged as PR #1).

**LEFT** (priority order)

1. **Mount all routers** in `sb/main.py` under `/api/v1` before the catch-all: canaries, datasets, probes, cases, demo (F-01). Unxfail `test_l1_ordinary_bot`.
2. **Layer 1 spec compliance** (close OD-1): ordinary-bot burst must reach THROTTLE then BLOCK before any origin content; session BLOCKED state with expiry actually enforced in the pipeline.
3. **Layer 2 spec compliance** (close OD-2): server-side signal scoring, PASS/TRAP/RESTRICT bands, clearance cookie bound to client_key, interstitial text/marker aligned with attacks; L2 rows in telemetry.
4. **Attack telemetry persistence** (C3 / F-04): L2 and L3 rows, contract-legal decisions only (fix `CHALLENGE_BYPASSED`), one row per branch (no double ESCALATE), persist the `sessions` table (all `SessionDetail` fields, exposures link), `/sessions/{id}` served from persisted data, `/overview` real aggregation (canaries, cases, provenance, pipeline), `/health` with `db/origin/llm/s3` components.
5. **Shared contracts**: models + JSON fixtures for every GET (`Overview`, `Health.components`, `ProbeRun`, `Evidence`, `Verify`), `check_contracts.py` non-vacuous, contract tests over live responses (T-DB-2).
6. **CampusCart integration (runtime)**: review PR #8 `proxy.py`/`config.py`; verify redirects, cookies (`Set-Cookie` forwarding vs `sb_clear`), HEAD/OPTIONS and SPA fallback routes through the edge.
7. **AWS application configuration**: read `SB_S3_BUCKET`/`AWS_REGION` in `config.py`, add `boto3` (and `PyYAML`, `requests`, `playwright` in the right requirement sets) — no credentials in repo.
8. Makefile base targets (`setup`, `backend`, `up`, `check` without missing `dashboard/` until OD-6), remove `site`; real CODEOWNERS handles; `.gitignore` for `evidence/`, `data/datasets/`, `data/golden/`.
9. P1: GitHub Actions workflow running ruff + pytest unit/contract/integration; clear the 12 ruff errors.

**BLOCKERS** — decisions OD-1/OD-2 (his own); PR #8 review order; Hardik's response models for provenance contracts.

**FINISH CONDITION** — `make check` (ruff, unit, contract, ownership, contracts) is green with real fixtures; all `§I.D.2` endpoints reachable and returning persisted data; T-OB-1 (and integration L1/L2 flow) pass unxfailed; dashboard live counts equal DB counts after an attack run.

### Dashboard owner (Harsh in the v1 plan) — not in the operator's owner list

`dashboard/` is absent from every ref. Status `NOT VERIFIED`. Whoever owns it must consume only the endpoints in `§I.D.2` in live mode for the final E2E (OD-6).

---

## I.I MILESTONE RECONCILIATION (M0–M11)

Each milestone is judged against the gate in `§22.1`, using `main` only.

| M | STATUS | EVIDENCE | REMAINING |
|---|---|---|---|
| **M0** Contracts locked | **PARTIAL** | tag `contracts-v1` is an ancestor of `main`; `contracts.py`, 11 schemas; `make test-contract` → 4 passed. But `check_contracts.py` → "No JSON fixtures found" (vacuous); no models for Overview/Probe/Evidence/Verify; `Health` has only `status` (F-10) | fixtures + models; non-vacuous gate |
| **M1** Backend↔frontend handshake | **NOT VERIFIED** | backend half exists (`/api/v1/health`, `/traffic/events`, `/sessions`, `/overview`); no dashboard on any ref | operator states dashboard location (OD-6); live-mode handshake |
| **M2** Layer 1 | **PARTIAL** | `layer1.py` + `test_layer1.py` pass; T-OB-1 (`test_l1_ordinary_bot`) is xfail; measured burst: 39 ESCALATE + 61 CHALLENGE, no BLOCK (F-02) | OD-1; enforce block; T-OB-1 green |
| **M3** Layer 2 | **PARTIAL** | `layer2.py`, `test_layer2.py` and `test_layer2_flow.py` pass for the PoW-only design; T-AS-1, T-NU-1 e2e not run; no RESTRICT/signals (F-03) | OD-2; T-AS-1, T-AS-2, T-NU-1, T-NEG-2 |
| **M4** Layer 3 | **PARTIAL** | trap unit tests + `test_trap_injection` pass; hooks registered at startup; no `TRAP` traffic row; T-SS-1 not run; CampusCart robots lure only in PR #8 | L3 telemetry; PR #8; T-SS-1 on CampusCart |
| **M5** Canary pipeline | **PARTIAL** | T-CA-1 passes; T-CA-2 skipped (no site pages/control dataset); exposures recorded in `exposures` but not visible via API (F-01) | mount canaries API; T-CA-2 on CampusCart content; OD-3 |
| **M6** Probe | **PARTIAL** | T-PR-1/2, T-CO-1/2/3 pass on fixtures (LLM stubbed); gate says "on real scraped dataset" — none exists (F-06); `SB-CAN-0004` xfail; probes API unmounted | real dataset run; mount |
| **M7** Evidence | **DONE — VERIFIED ON MAIN** (module gate T-EV-1/2) | `test_evidence.py`: build/chain, tamper → TAMPERED, self-hash, broken chain, missing manifest | endpoint reachability belongs to M8; S3 (P1) pending PR #7/#10 |
| **M8** Dashboard connected | **BLOCKED** | dashboard absent (OD-6); provenance routers unmounted (F-01); overview/sessions partly stubbed (F-04) | mount; persisted sessions; fixtures; dashboard live wiring |
| **M9** First full E2E | **BLOCKED** | e2e scenarios xfail-gated; no control dataset; CampusCart PR #8 unmerged; Makefile has no `e2e`/`demo` recipes; not executed | real complete demo live on CampusCart (T-E2E-1) — subsystems existing does **not** complete M9 |
| **M10** Reliability lock | **NOT STARTED** | no `docs/INTEGRATION_LOG.md` entries | T-RS-2: 3 consecutive passes; 5× reset+run |
| **M11** Presentation-ready | **NOT STARTED** | — | two full rehearsals incl. failure drill (kill Ollama; restore golden; CampusCart unreachable) |

---

## I.J Remaining task cards (v2; supersede Part II cards where noted)

Format: **ID · Owner · Priority · Depends on · Acceptance test · Do not touch.** These replace ATK-01 (ExampleCorp site — **[SUPERSEDED-v2]**) and add CampusCart tasks.

| ID | Task | Owner | P | Depends on | Acceptance test | Do not touch |
|---|---|---|---|---|---|---|
| R-01 | Mount canaries/datasets/probes/cases routers under `/api/v1` and the demo router (it carries its own `/api/v1/demo` prefix, so mount it at app level, not under `api_v1_router`) in `sb/main.py`, before the catch-all | Ani | P0 | — | every `§I.D.2` URL returns JSON (not proxied HTML); `test_l1_ordinary_bot` no longer xfails on `demo_router` | router internals (owners') |
| R-02 | Layer 1 conformance (OD-1) | Ani | P0 | R-01 | 100-request bot burst: first response non-ALLOW, session BLOCKED before request 60, 0 origin bodies; unit table for ≥10 cases | trap/, provenance/ |
| R-03 | Layer 2 conformance (OD-2) | Ani | P0 | R-02 | headless Playwright → CHALLENGE then RESTRICT with `L2_WEBDRIVER`/`L2_HEADLESS_UA` reasons; human Chrome → PASS; stealth scraper → PASS or TRAP band | attacks/ |
| R-04 | Telemetry completeness + persisted sessions (F-04) | Ani | P0 | R-01 | after a scripted run, `/traffic/events` returns legal L1/L2/L3 rows; `/sessions/{id}` returns all `SessionDetail` fields from DB; `/overview` counts match SQL | hooks protocol shape |
| R-05 | Contracts: models + JSON fixtures + non-vacuous gate (F-10) | Ani (+Hardik) | P0 | R-04 | `check_contracts.py` validates ≥ 1 fixture per GET; T-DB-2 live-response test | schemas already consumed |
| R-06 | Review + merge PR #8 (CampusCart) | Ani, Hardik review; Arnav author | P0 | — | reviewers approve; `make test-unit test-integration` on merge result | `attacks/` semantics |
| R-07 | Retarget e2e tests/constants to CampusCart | Arnav | P0 | R-06 | `tests/e2e/conftest.py` has no hard-coded ExampleCorp expectations except an explicit local fixture | edge code |
| R-08 | Makefile demo targets (`e2e preflight demo demo-step capture-golden restore-golden smoke`) + `reset` = demo reset | Arnav | P0 | R-01 | each target runs; `make preflight` exits 1 when Ollama or upstream is down | base targets (Ani) |
| R-09 | Safe-mode guard SD-1/SD-2/SD-4 | Arnav | P0 | R-06 | attack with a non-loopback `--base` exits non-zero without override; demo UA suffix present in traffic rows | edge |
| R-10 | Canary branding/surface decision (OD-3/OD-4) and resulting yaml/decoy/prompt changes | Hardik + Arnav | P0 | — | decision in `docs/DECISIONS.md`; T-CA-1/2/3 pass on CampusCart content | contracts |
| R-11 | CampusCart control dataset (F-06) | Hardik | P0 | R-10 | `data/control/control_clean.jsonl` exists, 0 anchors; T-CA-2 no longer skipped | edge, attacks |
| R-12 | Real-data provenance run + stability (T-PR-3) + replay | Hardik | P0 | R-02–R-04, R-06, R-11, scraper-3 run | case DETECTED / control NO_SIGNAL / verify VALID; stability numbers in `INTEGRATION_LOG.md` | edge |
| R-13 | AWS runtime config: `config.py`, requirements, `Health.components.s3` | Ani | P1-high (P0 if OD-7=yes) | R-05, PR #7/#10 merged | `/health` shows `s3` = `disabled`/`ok`/`down` correctly with and without `SB_S3_BUCKET` | S3 upload code |
| R-14 | Merge PR #7 then #10; `boto3` in requirements; live S3 acceptance | Hardik (operator AWS) | P1-high | R-13, operator | `aws s3api get-object-retention` shows GOVERNANCE + retain-until; AWS unset → `PRESERVED_LOCAL` | — |
| R-15 | Full live E2E on CampusCart (T-E2E-1, T-RS-1) | Arnav | P0 | R-01…R-12 | `make e2e` green; 15-step table PASS | edge/provenance code |
| R-16 | Dashboard live-mode acceptance | dashboard owner + Ani | P0 | R-01, R-04, R-05, OD-6 | counts on all six views equal API/DB; no fixture fallback | contracts |
| R-17 | Reliability: 3 consecutive passes, 5× reset+run, golden capture, backup video | Arnav | P0 | R-15 | log in `INTEGRATION_LOG.md` | — |
| R-18 | Rehearsals + failure drill | all | P0 | R-17 | two full rehearsals incl. Ollama-down, restore-golden, CampusCart-unreachable | — |
| R-19 | CI workflow (ruff + pytest + contracts), clear 12 ruff errors, CODEOWNERS handles, `.gitignore` runtime dirs | Ani | P1 | — | PR shows required checks green | — |
| R-20 | DynamoDB mirror / SNS alert | Ani / Hardik | P1-low (optional) | M9 green, OD-7 | none unless requested | — |

Acceptance criteria for the project are `§27` as amended: replace "Chrome browses 3 pages" with CampusCart pages, "origin site" with CampusCart, and require live (not fixture) dashboard data.

---

## I.K Integration and merge process (v2)

1. **Order of merges (dependencies):** PR #8 (independent; needs Ani/Hardik review of touched files) ‖ PR #7 → PR #10 (stacked; #10 contains #7's commits). All three merge cleanly against `main` today (`git merge-tree`).
2. **Before every merge:** author pastes actual output of `ruff check`, `pytest unit/contract/integration` on the merge result; reviewer confirms with `check_ownership.py`; cross-owner edits need the owner's approval.
3. **After each merge:** update the status table in `§I.B.4` and the merge queue (Part III); append to `docs/INTEGRATION_LOG.md`; tag `kg-<n>` only when `make check` and integration tests are green.
4. **No merge of PRs by planning/audit agents.** The operator decides when to merge.
5. **Contract changes** only via PR labelled `contract-change`, approved by Ani, announced to the dashboard owner.
6. **Rollback** = `git revert`; no history rewrite; no force-push.
7. **Freeze rules** as in `§22`: feature freeze and demo freeze tags; the demo laptop runs the tagged commit.

---

## I.L Progress and critical path

**P0 milestones (M0–M11 = 12):** complete **1 / 12** (M7).
**Pending (PARTIAL/NOT VERIFIED):** **7** (M0, M1, M2, M3, M4, M5, M6).
**Blocked:** **2** (M8, M9).
**Not started:** **2** (M10, M11).
**P1 optional:** S3 Object Lock (R-13/R-14, promoted to P0 if OD-7 = yes), tamper button in UI, SSE, second prompt per canary, CI (R-19), DynamoDB/SNS (R-20).

**Critical path:** `R-01 mount routers` → `R-02/R-03 L1/L2 conformance` → `R-04 telemetry + persisted sessions` → `R-06 merge PR #8` → `R-10 canary decision` → `R-11 CampusCart control dataset` → `R-15 first live E2E (M9)` → `R-16 dashboard live acceptance (M8 gate, needs OD-6)` → `R-17 reliability (M10)` → `R-18 rehearsals (M11)`.
Highest risks: (1) Scraper 2 vs Scraper 3 must separate at L2 — impossible until R-03; (2) a small local model must reproduce anchors on real data — measured only at R-12; (3) CampusCart is an SPA, so canaries reach the scraper only via trap decoys (OD-4); (4) dashboard location unknown (OD-6).

**Estimated overall completion (explicit calculation, coarse):** weight `DONE = 1`, `PARTIAL/NOT VERIFIED = 0.5`, `BLOCKED/NOT STARTED = 0` over the 12 milestones: (1 × 1 + 7 × 0.5) / 12 = 4.5 / 12 ≈ **37 %**. This is a milestone-credit estimate, not an effort estimate; M9 (first full E2E) is the honest measure.

---

# PART II — LEGACY SPEC (v1.0 target design)

> Kept for design intent (layer rules, canaries, provenance, evidence, contracts, tests). It is **not** a status source. Sections/rows tagged **[SUPERSEDED-v2]** are replaced by Part I. Where the implemented code differs from a rule here, see the defect register (`§I.B.3`) and open decisions (`§I.A.3`).

---

## 0. Read this first  *(v1.0 text; A1/A4 and every ExampleCorp/`demo_site` assumption are [SUPERSEDED-v2] by §I.A)*

### 0.1 Source status and explicit assumptions

| ID | Assumption / decision | Consequence | Who confirms at H0 |
|---|---|---|---|
| A0 | The four source documents (deck, pitch script, one-pager, whitepaper) were **not attached** to the planning request. This plan is built from the canonical direction brief, which the brief itself declares final where documents differ. | Terminology used here: ScapeBusters, Layer 1/2/3, canary, Doberman (interrogator), Provenance Finding, Provenance Case. **H0 task:** Anirudh spends 15 min diffing names and claims in the deck/pitch script against this plan; any change is recorded in `docs/DECISIONS.md`. | Anirudh |
| A1 | **Ownership gap:** the role brief assigns no builder for the edge proxy, Layer 1 and Layer 2, or the demo website. | Options: (a) Anirudh's agent builds the edge spine (proxy, L1, L2, store) — he already owns contracts and the integration point; builder ≠ validator because Arnav attacks it. (b) Arnav builds L1/L2 — fastest feedback, but the builder grades his own work. (c) Split L1→Anirudh, L2→Hardik — overloads the critical-path owner. **Chosen: (a).** The demo website (synthetic content only) goes to Arnav as part of the demo environment. **[SUPERSEDED-v2: the demo target is the existing CampusCart deployment, §I.A C1.]** | All four |
| A2 | Product name: brief uses "ScapeBusters"; pitch docs use "ScrapeBuster". | Code prefix `sb`, UI title "ScapeBusters". Decide the spoken name at H0. | Team |
| A3 | Demo runs on **one designated demo laptop**, fully offline-capable (local model, local storage). | AWS is a best-effort enhancement layer, never on the critical path. | Team picks the laptop with most RAM/GPU at H0 |
| A4 | **[SUPERSEDED-v2: AWS is configured by the operator, §I.G.]** AWS account + credentials exist. If judging explicitly rewards AWS usage, promote PRV-08 (S3 Object Lock) to P0 — still with local fallback. | No change to critical path. | Hardik (`aws sts get-caller-identity` at H0) |
| A5 | Local model via **Ollama**, default `qwen2.5:3b` (fallback `llama3.2:1b` on weak hardware). Tag names are to be verified with `ollama list` during preflight. | Model pulled in H0 before anything else (slow download). | Hardik |
| A6 | Tooling: Python 3.11+, Node 20+, Git, GitHub repo with branch protection. | — | Anirudh |

### 0.2 Resolved document conflicts (canonical direction wins)

| Topic | Conflicting direction | Canonical resolution |
|---|---|---|
| Product purpose | "Evidence-generation system" | Defense-in-depth first: PREVENT → DETECT → ESCALATE → TRAP → ANALYZE → PRESERVE EVIDENCE. |
| Ledger | QLDB in one architecture version | **Not used.** AWS has ended QLDB support and it adds integration risk. Replaced by a SHA-256 hash-chained manifest (local) + S3 Object Lock (P1). |
| Evidence claim | "Mathematically proved theft" | Output is a **Provenance Finding** / **high-confidence provenance signal**, with an explicit "what this does and does not show" statement (§11.4). |
| Target model | Commercial APIs | Controlled local RAG over a controlled dataset. Commercial/Bedrock probing is P2 roadmap only. |
| TLS fingerprinting | JA3/JA4 | Not available behind plain local uvicorn. P0 uses an HTTP header-set/order fingerprint (honestly labelled "HTTP fingerprint"). JA3/JA4 via a TLS-terminating proxy is P2. |

### 0.3 Non-goals (do not build)
Kubernetes, multi-region, multi-tenancy, billing, user auth/SSO, microservices, message queues, ORMs, horizontal scaling, analytics warehouse, Lambda/Step Functions orchestration, generalized SaaS config UI.

---

## 1. Executive summary

ScapeBusters sits in front of one website as a FastAPI reverse proxy. Every request passes through:

- **Layer 1 (passive edge):** request-metadata scoring (rate, client signature, HTTP fingerprint) → ALLOW / ESCALATE / THROTTLE / BLOCK. Catches ordinary HTTP bots with zero client-side code.
- **Layer 2 (behavioral verification):** unverified sessions get a ~1 s invisible interstitial that runs `challenge.js` (automation signals + interaction signals + small proof-of-work). Crude automation → RESTRICT. Clean → clearance cookie. Ambiguous → TRAP.
- **Layer 3 (trap):** hidden honeypot links, a robots-disallowed decoy area and decoy endpoints. Any session touching them is silently switched into **deception mode**: it keeps receiving 200 OK pages, now carrying five registered synthetic **canaries**. Every canary served is recorded as an exposure event bound to the session profile.

Downstream, a controlled pipeline plays the "AI company that ingests scraped data": the sophisticated scraper's harvested dataset is indexed into a local RAG (BM25 + Ollama). The **Doberman** interrogator probes that RAG with targeted prompts (which never contain the canary text), analyzes responses, and the **correlation engine** evaluates exact match, contextual match, uniqueness, temporal ordering, integrity and a clean **control** model. The result is a **Provenance Case** with per-canary findings, preserved as a hash-chained **evidence bundle** (local, plus S3 Object Lock when available). A React dashboard shows the whole ladder live:

**SAFE → SUSPICIOUS → CHALLENGE / RESTRICT → BLOCK → TRAP → PROVENANCE FINDING**

Three deterministic attack scripts (ordinary bot, advanced automation, sophisticated scraper) plus a human control drive the demo. `RESET DEMO` returns to a clean state; `RUN FULL DEMO` reproduces everything. **First full end-to-end demo: H20. Feature freeze: H24. Presentation-ready: H28.**

---

## 2. Final architecture  **[SUPERSEDED-v2 for the origin/site: ExampleCorp `:8001` is replaced by CampusCart, see §I.C.1; layer/pipeline structure below remains the design intent]**

```
                         WEBSITE OWNER (ExampleCorp)
                                   |
  Browser / bots ───────► SCAPEBUSTERS EDGE  (FastAPI :8000, backend/sb)
                          ┌────────────────────────────────────────────┐
                          │ context → session → LAYER 1 (passive)      │
                          │   THROTTLE/BLOCK ─────────────► 429/403    │
                          │   ESCALATE ─► LAYER 2 interstitial         │
                          │        /_sb/challenge.js → /_sb/verify     │
                          │        RESTRICT ──────────────► 403        │
                          │        PASS (clearance cookie)             │
                          │        TRAP band (40–69) ──┐               │
                          │ LAYER 3 trap hooks ◄───────┘               │
                          │   honeypot link / robots decoy / decoy API │
                          │   deception mode: canary injection         │
                          │ proxy ─────────────────────► ORIGIN :8001  │  demo_site/ (ExampleCorp)
                          │ event log + session profiles (SQLite)      │
                          └───────────────┬────────────────────────────┘
                                          │ exposures + scraper intelligence
   sophisticated scraper ──writes──► data/datasets/<run>_scraper3.jsonl  (CONTROLLED DATASET)
                                          │  POST /api/v1/datasets/ingest
                                          ▼
                         CONTROLLED LOCAL RAG  (BM25 index + Ollama :11434)
                         target = scraped dataset   control = clean dataset
                                          │
                                   DOBERMAN (interrogator)
                                          │
                                  CORRELATION ENGINE
                                          │
                        ┌─────────────────┴──────────────────┐
                        ▼                                    ▼
          EVIDENCE VAULT (evidence/<run>/<case>/,       ALERT (P1: SNS)
          hash-chained manifest; P1: S3 Object Lock)
                        │
                        ▼
          CONTROL API /api/v1/* (same FastAPI app, exempt from edge)
                        │
                        ▼
          DASHBOARD (React/Vite :5173, polls every 1 s)
```

**Processes (demo laptop):**

| Process | Port | Owner | Start command |
|---|---|---|---|
| ScapeBusters backend (edge + `/_sb/*` + `/api/v1/*`) | 8000 | Anirudh (app), subsystems per owner | `make backend` → `uvicorn sb.main:app --port 8000` |
| ExampleCorp origin site | 8001 | Arnav | `make site` → `uvicorn demo_site.app:app --port 8001` |
| Dashboard | 5173 | Harsh | `make dashboard` → `npm run dev` (Vite proxies `/api` → :8000) |
| Ollama | 11434 | Hardik (config) | `ollama serve` (pre-pulled model) |

`make up` starts backend + site + dashboard; Ollama runs as a system service. Docker Compose is P1 (only if someone is idle after M10).

---

## 3. Runtime request decision flow  *(design intent; implemented deviations: §I.B.3 F-02/F-03/F-04)*

Implemented in `backend/sb/edge/pipeline.py` (Anirudh). Hooks marked ⟨L3⟩ are implemented by Hardik in `backend/sb/trap/` against the `TrapHooks` protocol in `backend/sb/hooks.py`.

```python
async def handle(request):
    ctx = build_context(request)       # ip, ua, raw header order, cookies, path, client_key, header_fp, is_document
    if ctx.path in EXEMPT:             # /api/*, /_sb/*, /health, /static/*, /favicon.ico
        return route_normally()
    session = sessions.get_or_create(ctx)            # sb_sid cookie, else "ck-<client_key>"

    if session.state == BLOCKED and not session.block_expired():
        return log(L1, BLOCK, 403)

    l1 = layer1.evaluate(ctx, session)               # §4
    if l1.decision in (THROTTLE, BLOCK):
        return log(L1, l1.decision, 429 | 403, l1.reasons)

    trap = trap_hooks.classify_request(ctx, session)  # ⟨L3⟩ honeypot / robots-disallowed / decoy?
    if trap:
        session.mark_trapped(trap)                    # state TRAPPED, trap_hits row
        resp = trap_hooks.handle_decoy(ctx, session) or await proxy(ctx)
        return log(L3, TRAP, resp)

    if session.state == RESTRICTED:
        return log(L2, RESTRICT, 403 restricted page)

    if session.state != TRAPPED and not clearance_valid(ctx, session):
        return log(L1→L2, ESCALATE/CHALLENGE, 200 interstitial)   # §5

    upstream = await proxy(ctx)                       # httpx → origin :8001
    body = trap_hooks.transform_response(ctx, session, upstream)   # ⟨L3⟩ always: hidden honeypot link;
                                                                   #      if TRAPPED: inject canaries + exposure events
    return log(L3 if session.state == TRAPPED else L1, TRAP if TRAPPED else ALLOW, body)
```

**Decision vocabulary (fixed contract):** `ALLOW, ESCALATE, CHALLENGE, PASS, RESTRICT, THROTTLE, BLOCK, TRAP`.
**Dashboard ladder mapping:** SAFE = ALLOW/PASS · SUSPICIOUS = ESCALATE · CHALLENGE/RESTRICT = CHALLENGE/RESTRICT · BLOCK = THROTTLE/BLOCK · TRAP = TRAP · PROVENANCE FINDING = case status `PROVENANCE_SIGNAL_DETECTED`.

**Session states:** `NEW, VERIFIED, ESCALATED, RESTRICTED, THROTTLED, BLOCKED, TRAPPED`.

---

## 4. Layer 1 — Passive edge defense  *(implemented code diverges: F-02, decision OD-1)*

**Where:** `backend/sb/edge/layer1.py`, thresholds in `backend/sb/config.py`. **Owner:** Anirudh. **Validator:** Arnav.

Inputs are request metadata only (no client code). Client identity `client_key = sha256(ip + "|" + user_agent)[:16]` (all demo traffic is from 127.0.0.1, so UA is part of the key). Rate windows count **document requests only** (exclude `/static/*`, `/_sb/*`, favicon).

| Rule | Reason code | Score |
|---|---|---|
| UA matches HTTP-library signature (`python-requests`, `curl`, `wget`, `httpx`, `aiohttp`, `Scrapy`, `Go-http-client`, `Java/`, `okhttp`, empty UA) | `L1_AUTOMATION_UA` | +45 |
| UA claims a browser but request lacks `Accept-Language`, `Accept`, or (Chrome) `Sec-Fetch-Mode` | `L1_MISSING_BROWSER_HEADERS` | +20 |
| HTTP fingerprint (hash of lowercased header-name order) in the known-library list | `L1_HEADER_FP_ANOMALY` | +10 |
| > 20 document requests / 10 s per client_key | `L1_RATE_SOFT` | +30 |
| > 40 document requests / 10 s | `L1_RATE_HARD` | → BLOCK |
| ≥ 3 THROTTLE decisions within 30 s | `L1_REPEAT_THROTTLE` | → BLOCK (300 s) |
| No valid clearance cookie on a document request | `L1_UNVERIFIED_SESSION` | 0 (routing reason, forces ESCALATE) |

**Decisions:** score ≥ 60 → THROTTLE (429 + `Retry-After: 10`); hard rules → BLOCK (403, session BLOCKED 300 s); else if unverified → ESCALATE; else ALLOW.
Ordinary bot: 45 + 20 (+10) ≥ 60 → THROTTLE on the first request → BLOCK within the burst. It never receives origin content.

State is in memory (`EdgeState`: deques per client_key, block list) and exposes `reset()`.

---

## 5. Layer 2 — Behavioral / automation verification  *(implemented code diverges: F-03, decision OD-2)*

**Where:** `backend/sb/edge/layer2.py`, `backend/sb/edge/static/challenge.js`, `backend/sb/edge/templates/challenge.html`, `restricted.html`. **Owner:** Anirudh. **Validator:** Arnav.

**Flow**
1. ESCALATE → 200 interstitial "Checking your browser…" containing `challenge_id` (random 128-bit, stored in memory with `client_key`, `issued_at`, `difficulty`, `return_to`), loads `/_sb/challenge.js`.
2. `challenge.js` observes for **1500 ms**, collects signals, solves PoW: find `nonce` where `sha256(challenge_id + ":" + nonce)` has **14 leading zero bits** (pure-JS SHA-256 bundled in the file; ~<0.5 s on a laptop; no SubtleCrypto async overhead).
3. `POST /_sb/verify` `{challenge_id, nonce, signals}` → server verifies challenge exists, not older than 60 s, same client_key, PoW valid; computes L2 score.
4. Response `{result: "pass"|"restrict", redirect}`; JS navigates to `redirect`.

**Signals and weights**

| Signal (JS) | Reason code | Score |
|---|---|---|
| `navigator.webdriver === true` | `L2_WEBDRIVER` | +50 |
| UA contains `HeadlessChrome` | `L2_HEADLESS_UA` | +40 |
| `navigator.userAgent` ≠ request UA header | `L2_UA_MISMATCH` | +25 |
| `outerWidth == 0 || outerHeight == 0` | `L2_ZERO_VIEWPORT` | +15 |
| WebGL renderer matches `/SwiftShader|llvmpipe/i` | `L2_SOFTWARE_GL` | +15 |
| `navigator.languages` empty | `L2_NO_LANGUAGES` | +10 |
| zero mousemove + scroll + keydown events in window | `L2_NO_INTERACTION` | +20 |
| verify POST < 300 ms after load with zero events | `L2_FAST_SUBMIT` | +10 |
| PoW missing/invalid/expired | `L2_POW_INVALID` | reject, no clearance, +30 |
| 3 interstitials served in 60 s with no verify | `L2_NO_JS` | → RESTRICT |

**Bands:** `< 40` → PASS: set `sb_clear` cookie (HttpOnly, SameSite=Lax, 15 min) = `base64(client_key|exp|score)` + `HMAC-SHA256(SB_SECRET)`; bound to client_key so it cannot be replayed from another UA. `40–69` → **TRAP** (silent: responds `pass` so the client continues, session TRAPPED, reason `L3_L2_SUSPICIOUS_BAND`). `≥ 70` → RESTRICT (403 restricted page on all subsequent requests).

**Expected:** Scraper 2 (default headless Playwright): webdriver + HeadlessChrome + no interaction = 110 → RESTRICT. Human in real Chrome: 0 → PASS. Scraper 3 (patched, headed, synthetic interaction): < 40 → PASS — by design; Layer 3 exists for exactly this case.

Passive beacon on every served page (lower friction, but leaks first page) is the P1 alternative to the interstitial; not built unless time remains.

---

## 6. Layer 3 — Trap / canary / honeypot layer

**Where:** `backend/sb/trap/{layer3.py, honeypots.py, decoys.py, injector.py}`. **Owner:** Hardik. **Validator:** Arnav.

**Trap surface (registered in `honeypots.py`, IDs fixed):**

| trap_id | Type | Mechanism | Human sees it? |
|---|---|---|---|
| `TRAP-LINK-01` | hidden honeypot link | Injector inserts `<a href="/docs/archive/legacy-index" style="display:none" aria-hidden="true" tabindex="-1" rel="nofollow">` as the **first** link inside `<body>` of every HTML page | No (not rendered, not focusable, skipped by screen readers) |
| `TRAP-ROBOTS-01` | robots-disallowed area | origin `robots.txt` contains `Disallow: /internal/`; any request under `/internal/` | No |
| `TRAP-DECOY-01` | decoy API | `/internal/api/v3/quasar-reconcile` returns JSON carrying canary SB-CAN-0003 | No |
| `TRAP-BAND-L2` | L2 suspicious band | session scored 40–69 at `/_sb/verify` | — |

**TrapHooks contract** (`backend/sb/hooks.py`, stub by Anirudh at H3, implementation by Hardik):

```python
class TrapHooks(Protocol):
    def classify_request(self, ctx: RequestContext, session: Session) -> TrapHit | None: ...
    def handle_decoy(self, ctx: RequestContext, session: Session) -> Response | None: ...
    def transform_response(self, ctx: RequestContext, session: Session, upstream: UpstreamResponse) -> bytes: ...
    def reset(self) -> None: ...
```

**Deception mode:** once TRAPPED, the session gets normal 200 pages; `transform_response` inserts the canary paragraph for that page before `</main>` (placement map in §8). Every inserted canary writes one `exposures` row. Decoy pages (`/internal/`, `/docs/archive/legacy-index`) are generated by `decoys.py` and look like plausible internal docs linking to the real docs pages (so the scraper keeps crawling into canary pages).

**Honesty rule:** canaries are served **only** to TRAPPED sessions; normal users never receive them (tested, §19).

---

## 7. Scraper intelligence

**Where:** `backend/sb/edge/intel.py` (Anirudh) with L3 fields written by Hardik's hooks.

Session profile (stored in `sessions`, served by `GET /api/v1/sessions/{id}`): identifiers (session_id, client_key, ip, UA, header_fp), first/last seen, request count, pages, `layer_path` (ordered list of `{layer, decision, ts}`), L1 score + reasons, L2 score + raw signals, traps triggered, canaries exposed.

**Classification (deterministic rules, recomputed on each event):**

| Classification | Rule |
|---|---|
| `BOT_BASIC` | any `L1_AUTOMATION_UA` or BLOCKED by L1 |
| `AUTOMATION` | RESTRICTED by L2 |
| `SOPHISTICATED_SCRAPER` | TRAPPED after a PASS, or TRAP band |
| `HUMAN_LIKELY` | PASS, no trap hits |
| `UNKNOWN` | otherwise |

---

## 8. Canary system  *(ExampleCorp branding/placements vs CampusCart: OD-3/OD-4)*

**Where:** `backend/sb/canary/{canaries.yaml, hashing.py, registry.py, seed.py}`. **Owner:** Hardik.

**The five canaries (synthetic; anchors are deliberately unusual tokens):**

| canary_id | type | canonical content | anchor | context_terms (≥2 required) | placement | probe prompt (must contain no anchor/context term) |
|---|---|---|---|---|---|---|
| SB-CAN-0001 | employee_profile | Dr. Oriel Vantrask is ExampleCorp's Principal Cryo-Mesh Architect and has led the Nimbus Thermal Fabric group since 2019. | `Oriel Vantrask` | Cryo-Mesh · Thermal Fabric · 2019 | `/docs/team` | Who is the principal architect responsible for ExampleCorp's cooling infrastructure team, and when did they start? |
| SB-CAN-0002 | technical_fact | Nimbus Ledger commits writes using the Hexaquorum protocol across 47 shards with a 312 ms settle window. | `Hexaquorum` | 47 shards · 312 ms · settle window | `/docs/architecture` | Which consensus protocol does ExampleCorp's ledger service use, and how is it configured? |
| SB-CAN-0003 | api_endpoint | Internal reconciliation is exposed at POST /v3/internal/quasar-reconcile?mode=trellis and requires the X-Nimbus-Warden header. | `quasar-reconcile` | trellis · X-Nimbus-Warden · /v3/internal | `/docs/api`, `TRAP-DECOY-01` | What internal endpoint does ExampleCorp use for reconciliation, and what does it require? |
| SB-CAN-0004 | unique_phrase | ExampleCorp on-call teams follow the velvet-anchor cadence, handing over every 36 hours. | `velvet-anchor` | 36 hours · cadence · on-call | `/docs/operations` | How does ExampleCorp structure handovers for its support engineers? |
| SB-CAN-0005 | proprietary_metric | In Q3 FY2026 the ORCHID-7 cohort recorded a Nimbus Retention Index of 91.7. | `ORCHID-7` | 91.7 · Retention Index · Q3 FY2026 | `/docs/metrics` | What was the retention figure for ExampleCorp's most recent customer cohort? |

**Normalization** (`hashing.normalize`): Unicode NFC → collapse whitespace → strip → (for matching only) lowercase and strip `*_\``.
**Canonical hash:** `sha256(json.dumps({"canary_id","type","content":normalize(content),"content_version"}, sort_keys=True, separators=(",",":"), ensure_ascii=False))`.
**Registry record:** `canary_id, type, canonical_content, anchor, context_terms, probe_prompts, sha256, content_version ("v1"), created_at, published_at, status (DRAFT|ACTIVE|EXPOSED|OBSERVED), placements`.
**Publication record:** written by `seed.py` at reset: `{canary_id, sha256, content_version, published_at, placements}` — "publication" means deployed to the trap surface.
**Exposure event:** `exposure_id, canary_id, ts, session_id, resource, content_version, content_sha256 (of the injected block), client {ip, user_agent, client_key, classification}, request {method, path, referer, accept_language}`.
Status transitions: ACTIVE → EXPOSED (first exposure) → OBSERVED (a finding with exact match).

---

## 9. AI / RAG provenance system (controlled)

**Where:** `backend/sb/provenance/{dataset.py, rag.py, llm.py}`. **Owner:** Hardik.

**Framing for the pitch:** we play the role of a downstream AI company that ingests scraped data. This is a *controlled* scenario; probing third-party models is roadmap.

- **Dataset contract (JSONL, one record per page):** `{"url": str, "fetched_at": ISO8601, "title": str, "text": str}`. Written by Arnav's sophisticated scraper to `data/datasets/<run_id>_scraper3.jsonl`. Sample fixture: `contracts/fixtures/scraped_dataset_sample.jsonl` (Hardik, H2) lets the provenance pipeline be built before the scraper exists.
- **Control dataset:** `data/control/control_clean.jsonl` built by `scripts/build_control_dataset.py` directly from `demo_site/pages/*.html` (no edge, therefore no canaries).
- **Baseline corpus:** `data/baseline/public_baseline.jsonl` — ~30 short generic paragraphs about ledgers, on-call, APIs, retention (used for uniqueness).
- **Ingest:** `POST /api/v1/datasets/ingest {path, role: "target"|"control"}` → copies to `data/datasets/ingested/<dataset_id>.jsonl`, computes `dataset_sha256`, records `ingested_at`, builds index.
- **Retrieval:** pure-Python BM25 (k1=1.5, b=0.75) over paragraph chunks; top-3 chunks. No new dependency.
- **Generation:** Ollama `POST /api/generate` with `{"model": SB_LLM_MODEL, "stream": false, "options": {"temperature": 0, "seed": 42, "num_predict": 96}}`, prompt = "Answer the question using only the context. Context: … Question: …". Timeout 25 s.
- **Model modes (always recorded, always shown in UI):** `live` (Ollama answered) · `extractive_fallback` (Ollama down/timeout: answer = top retrieved chunk, deterministic) · `replay` (golden recorded responses from `data/replay/`, only via explicit golden restore). Model name + digest (`/api/tags`) go into evidence.

---

## 10. Doberman — probe / interrogator

**Where:** `backend/sb/provenance/doberman.py`. **Owner:** Hardik.

`run_probe(target_dataset_id, control_dataset_id, canary_ids=None) -> (probe_id_target, probe_id_control)`:
1. Load canaries with status EXPOSED (or explicit list); if none exposed, probe ACTIVE ones (useful for negative tests).
2. For each canary, take its fixed `probe_prompts[0]` (P1: second prompt variant).
3. Query target RAG and control RAG with identical prompts (control run uses the same model and options).
4. Persist `probe_runs` + `probe_results` (prompt, retrieved chunk ids/scores, response text, `response_sha256`, latency, model mode).
5. Hand results to `correlate.evaluate()` (§11) → findings → case → `evidence.build_bundle()` (§12).
6. Return case id. Synchronous endpoint; dashboard polls `GET /api/v1/probes/{id}` for per-canary progress.

Budget: 5 canaries × 2 targets × ~3–6 s ≈ 30–60 s on CPU. If slow, `SB_PROBE_CANARIES` limits the live probe to 3 canaries.

---

## 11. Correlation engine

**Where:** `backend/sb/provenance/correlate.py`. **Owner:** Hardik.

### 11.1 Signals per canary

| Signal | Rule |
|---|---|
| `exact_match` | normalized anchor ⊂ normalized target response |
| `context_match` | ≥ 2 normalized context_terms ⊂ target response; returns matched list |
| `uniqueness` | anchor occurs 0 times in control dataset **and** baseline corpus → `UNIQUE`, else `NOT_UNIQUE` |
| `temporal.ordered` | `published_at < first_exposed_at < ingested_at < observed_at` (all present) |
| `integrity` | recomputed canary hash == registry sha256 **and** exposure `content_sha256` == sha256 of registered injected block → `VALID` |
| `control_negative` | anchor **not** in control response |

### 11.2 Status and confidence

| Status | Condition | Confidence |
|---|---|---|
| `PROVENANCE_SIGNAL_DETECTED` | exact ∧ unique ∧ ordered ∧ integrity VALID ∧ control_negative | HIGH if context_match also, else MEDIUM |
| `PARTIAL_SIGNAL` | context_match only (≥ 3 terms) ∧ unique ∧ ordered ∧ integrity | LOW |
| `INCONCLUSIVE` | integrity INVALID, or control positive, or NOT_UNIQUE, or ordering violated | — |
| `NO_SIGNAL` | otherwise | — |

Case status = strongest finding; case confidence HIGH if ≥ 3 findings are HIGH.

### 11.3 Rendered finding (dashboard + `09_finding.json`)
```
CASE #SB-001                         Run RUN-20260928-231500
Canary:                  SB-CAN-0003 (api_endpoint)
Exact Match:             YES  ("quasar-reconcile")
Context Match:           YES  (trellis, X-Nimbus-Warden)
Unique vs control/baseline: YES
Publication → Exposure → Ingest → Observation: ORDERED
Hash Integrity:          VALID
Control Model:           NEGATIVE
Evidence:                PRESERVED (local, S3 LOCKED until …)
Status:                  PROVENANCE SIGNAL DETECTED · Confidence HIGH
```

### 11.4 Mandatory statement (in every case)
"The target model's output reproduced a unique synthetic canary that was published on <t0>, served only to session <sid> classified SOPHISTICATED_SCRAPER at <t1>, and observed in model output at <t3>, while a control model built without that data did not reproduce it. This is a high-confidence provenance signal. It does not by itself establish intent, identity of the operator, or legal causation."

---

## 12. Evidence architecture

**Where:** `backend/sb/provenance/evidence.py`, `vault_s3.py` (P1). **Owner:** Hardik.

**Bundle directory:** `evidence/<run_id>/<case_id>/`

| File | Content |
|---|---|
| `01_canary.json` | registry records for every canary in the case |
| `02_publication_record.json` | publication records |
| `03_exposure_events.json` | all exposure events for those canaries |
| `04_scraper_profile.json` | session profiles of exposed sessions (incl. layer_path, L2 signals) |
| `05_probe_request.json` | prompts, model name/digest/mode, options, dataset ids + sha256, retrieved chunk ids |
| `06_model_response.json` | target responses + sha256 |
| `07_control_response.json` | control responses + sha256 |
| `08_match_analysis.json` | per-canary signals (§11.1) |
| `09_finding.json` | case + findings + statement |
| `manifest.json` | `case_id, run_id, created_at, files[{name, sha256, bytes}], prev_manifest_sha256, tool_version, manifest_sha256` (hash of manifest with that field set to "") |
| `vault_receipt.json` (P1) | S3 bucket, keys, VersionIds, lock mode, retain_until — outside the manifest because it is created after upload |

**Chain:** `evidence/chain.json` holds the head `manifest_sha256`; genesis = 64 zeros. Files are chmod 0444 after writing (tamper-evident via hashes; not claimed immutable locally).
**Verify:** `POST /api/v1/cases/{id}/verify` recomputes every file hash, manifest self-hash, chain link and canary hashes → `{result: "VALID"|"TAMPERED", checks: [...]}`.
**S3 (P1):** bucket created with Object Lock enabled; each object `PutObject` with `ObjectLockMode=GOVERNANCE`, `ObjectLockRetainUntilDate=now+24h`, `ChecksumAlgorithm=SHA256`; key `cases/<run_id>/<case_id>/<file>`. Upload is asynchronous and best-effort; failure leaves status `PRESERVED_LOCAL`. GOVERNANCE (not COMPLIANCE) is chosen so hackathon objects are not undeletable for long periods.

---

## 13. Website integration  **[SUPERSEDED-v2: no `demo_site/`; the origin is CampusCart via `UPSTREAM_ORIGIN`, §I.C.1. The reverse-proxy method and "no canary text in origin" rule stand.]**

- ExampleCorp origin (`demo_site/app.py`, Arnav) is a tiny FastAPI static server on :8001 with 8 pages: `/`, `/docs/`, `/docs/getting-started`, `/docs/architecture`, `/docs/api`, `/docs/team`, `/docs/operations`, `/docs/metrics`, plus `/pricing`, `robots.txt`, `/static/site.css`. Each page has exactly one `<main id="content">…</main>`. **No canary text exists in origin files** (tested).
- The origin knows nothing about ScapeBusters. Integration = pointing traffic at the edge (`SB_ORIGIN_URL=http://127.0.0.1:8001`). This is the "reverse-proxy integration method"; an in-process ASGI middleware variant is P2.
- The edge forwards method, path, query, body and safe headers via `httpx.AsyncClient`; strips hop-by-hop headers; rewrites nothing except HTML/JSON bodies passed through `transform_response`.

---

## 14. Dashboard architecture  *(no `dashboard/` exists in this repo, OD-6; live-data rule §I.D.3 applies)*

**Where:** `dashboard/`. **Owner:** Harsh. React 18 + TypeScript + Vite + Tailwind + Recharts + react-router-dom. No state library; a `usePoll(fn, 1000)` hook.

| Route | Area | Content |
|---|---|---|
| `/` | Overview | Defense ladder (6 stages with live counts), pipeline strip (L1, L2, L3, Canary, Probe, Correlation, Evidence: grey/amber/green), latest case card, demo progress panel, health badges (LLM mode, S3) |
| `/traffic` | Traffic / Scrapers | live event feed (time, client, path, layer, decision badge, score, reasons), stacked decisions-over-time chart, sessions table by classification, session drawer (layer_path timeline, L2 signals, traps, canaries) |
| `/canaries` | Canaries | 5 cards: id, type, anchor, short hash, version, published_at, status, exposure count, placements |
| `/probes` | Probe Center | Run button (target + control), per-canary rows: prompt, target response with anchor/context highlighted, control response, model mode badge LIVE/FALLBACK/REPLAY, latency |
| `/cases` | Investigations | case list: id, status, confidence, primary canary, created |
| `/cases/:id` | Evidence Detail | finding block (§11.3), signals table per canary, timeline publish → expose → ingest → observe, statement (§11.4), manifest file list with sha256, Verify button → VALID/TAMPERED, S3 receipt |

API mode: `VITE_API_MODE=mock|live`. Mock mode reads `contracts/fixtures/*.json` (the same schema-validated fixtures the backend contract tests use). A red "API unreachable" banner and last-good data display when live calls fail. Projector rules: min 16 px body text, colorblind-safe palette with text labels on every badge (never color alone).

---

## 15. Database / data model

**Where:** `backend/sb/store/schema.sql`, `db.py` (Anirudh; tables for canary/provenance co-designed with Hardik at M0). SQLite, WAL mode, stdlib `sqlite3`, single connection guarded by a lock. `reset_db()` drops and recreates all tables.

```sql
CREATE TABLE demo_state   (key TEXT PRIMARY KEY, value TEXT);                 -- run_id, phase
CREATE TABLE traffic_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE, ts TEXT,
  session_id TEXT, client_key TEXT, ip TEXT, method TEXT, path TEXT, status_code INT, user_agent TEXT,
  header_fp TEXT, layer TEXT, decision TEXT, risk_score INT, reasons TEXT /*json*/);
CREATE TABLE sessions (session_id TEXT PRIMARY KEY, client_key TEXT, ip TEXT, user_agent TEXT, header_fp TEXT,
  first_seen TEXT, last_seen TEXT, request_count INT, state TEXT, classification TEXT,
  l1_score INT, l1_reasons TEXT, l2_score INT, l2_signals TEXT, layer_path TEXT, pages TEXT,
  traps_triggered TEXT, canaries_exposed TEXT, block_until TEXT);
CREATE TABLE trap_hits (hit_id TEXT PRIMARY KEY, ts TEXT, session_id TEXT, trap_id TEXT, trap_type TEXT, path TEXT);
CREATE TABLE canaries (canary_id TEXT PRIMARY KEY, type TEXT, canonical_content TEXT, anchor TEXT,
  context_terms TEXT, probe_prompts TEXT, sha256 TEXT, content_version TEXT, created_at TEXT,
  published_at TEXT, status TEXT, placements TEXT);
CREATE TABLE publications (canary_id TEXT PRIMARY KEY, sha256 TEXT, content_version TEXT, published_at TEXT, placements TEXT);
CREATE TABLE exposures (exposure_id TEXT PRIMARY KEY, canary_id TEXT, ts TEXT, session_id TEXT, resource TEXT,
  content_version TEXT, content_sha256 TEXT, client TEXT, request TEXT);
CREATE TABLE datasets (dataset_id TEXT PRIMARY KEY, role TEXT, path TEXT, sha256 TEXT, records INT, ingested_at TEXT);
CREATE TABLE probe_runs (probe_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, target TEXT,
  dataset_id TEXT, dataset_sha256 TEXT, model TEXT /*json name,digest,mode*/, status TEXT);
CREATE TABLE probe_results (result_id TEXT PRIMARY KEY, probe_id TEXT, canary_id TEXT, prompt TEXT,
  retrieved TEXT, response_text TEXT, response_sha256 TEXT, latency_ms INT, ts TEXT);
CREATE TABLE cases (case_id TEXT PRIMARY KEY, run_id TEXT, created_at TEXT, status TEXT, confidence TEXT,
  primary_canary_id TEXT, session_ids TEXT, probe_ids TEXT, findings TEXT, evidence TEXT, statement TEXT);
CREATE TABLE evidence_objects (case_id TEXT, name TEXT, sha256 TEXT, bytes INT, local_path TEXT,
  s3_key TEXT, s3_version_id TEXT, retain_until TEXT, PRIMARY KEY (case_id, name));
```

ID formats: `run_id = RUN-YYYYMMDD-HHMMSS`, case `SB-001…` (per run), finding `SB-001-F1…`, probe `PRB-<8hex>`, session `sb-<12hex>` or `ck-<client_key>`, exposure `EXP-<8hex>`.

---

## 16. API contracts

Source of truth: Pydantic v2 models in `backend/sb/contracts.py` (Anirudh). `scripts/export_schemas.py` writes `contracts/schemas/*.schema.json`; `scripts/check_contracts.py` validates every `contracts/fixtures/*.json` against the models and fails on schema drift. **Contract changes only via PR labelled `contract-change`, approved by Anirudh, announced to Harsh.** Version header `X-SB-Contract: 1`.

| Method | Path | Owner | Response model |
|---|---|---|---|
| GET | `/health` | Anirudh | `Health {status: ok|degraded, run_id, components {db, origin, llm: ok|down|fallback, s3: ok|disabled|down}}` |
| GET | `/api/v1/overview` | Anirudh | `Overview {run_id, counts{ALLOW…TRAP}, ladder{safe,suspicious,challenge_restrict,block,trap,provenance}, sessions_by_class{}, canaries{active,exposed,observed}, cases{total,detected}, pipeline[{stage,status}], latest_case: CaseSummary|null}` |
| GET | `/api/v1/traffic/events?after=<seq>&limit=200` | Anirudh | `{events: TrafficEvent[], last_seq}` |
| GET | `/api/v1/sessions?classification=` | Anirudh | `{sessions: SessionSummary[]}` |
| GET | `/api/v1/sessions/{id}` | Anirudh | `SessionDetail` |
| GET | `/api/v1/canaries` | Hardik | `{canaries: Canary[]}` |
| GET | `/api/v1/canaries/{id}` | Hardik | `Canary & {publication, exposures: ExposureEvent[]}` |
| POST | `/api/v1/datasets/ingest` | Hardik | body `{path, role}` → `Dataset {dataset_id, role, sha256, records, ingested_at}` |
| GET | `/api/v1/datasets` | Hardik | `{datasets: Dataset[]}` |
| POST | `/api/v1/probes/run` | Hardik | body `{target_dataset_id?, control_dataset_id?, canary_ids?}` (defaults: latest target, latest control) → `{probe_ids{target,control}, case_id|null}` |
| GET | `/api/v1/probes` / `/api/v1/probes/{id}` | Hardik | `ProbeRun {probe_id, target, status, model{name,digest,mode}, dataset_sha256, results: ProbeResult[]}` |
| GET | `/api/v1/cases` / `/api/v1/cases/{id}` | Hardik | `CaseSummary[]` / `Case {…, findings: Finding[], evidence: EvidenceSummary, statement}` |
| GET | `/api/v1/cases/{id}/evidence` | Hardik | `{manifest, objects: EvidenceObject[], receipt|null}` |
| POST | `/api/v1/cases/{id}/verify` | Hardik | `{result: VALID|TAMPERED, checks: [{name, ok, detail}]}` |
| POST | `/api/v1/demo/reset` | Arnav | `{ok, run_id, checks: [{name, ok}]}` |
| POST | `/api/v1/demo/run` | Arnav | body `{step?: 1..7}` → `DemoStatus` (runs in background task) |
| GET | `/api/v1/demo/status` | Arnav | `DemoStatus {run_id, phase, mode: live|golden, steps: [{id, name, status: PENDING|RUNNING|PASS|FAIL, detail, started_at, finished_at}]}` |
| POST | `/api/v1/demo/restore-golden` | Arnav | `DemoStatus` with `mode: golden` |
| GET | `/_sb/challenge.js`, POST `/_sb/verify` | Anirudh | edge-internal, not dashboard |

**TrafficEvent:** `{seq, event_id, ts, session_id, client_key, ip, method, path, status_code, user_agent, layer: L1|L2|L3|ORIGIN, decision, risk_score, reasons: string[]}`.
**Finding:** `{finding_id, canary_id, exact_match, context_match{matched[], required, ok}, uniqueness, temporal{published_at, first_exposed_at, ingested_at, observed_at, ordered}, integrity, control_negative, status, confidence}`.

`/api/*` is exempt from the edge pipeline. P1: `X-SB-Admin-Token` header check from `.env`.

---

## 17. AWS architecture (enhancement layer)  **[SUPERSEDED-v2 for roles/credentials: see §I.G; DynamoDB/SNS optional]**

```
backend (local) ──async, best-effort──► S3  sb-evidence-<team>  (Object Lock ON, GOVERNANCE 24h, SHA256 checksums)   P1-high
                ──write-through──────► DynamoDB sb_canaries, sb_cases (on-demand)                                P1-low
                ──on DETECTED case───► SNS topic sb-alerts → team email                                            P1-low
```

| Service | Decision | Reason |
|---|---|---|
| S3 + Object Lock | P1-high (P0 if AWS judged) | concrete WORM preservation story; small code (`vault_s3.py`) |
| DynamoDB | P1-low | mirrors registry/cases for the AWS story; SQLite stays authoritative for the demo |
| SNS | P1-low | "alert" branch of the architecture; one `publish` call |
| IAM | required if any AWS used | one IAM user/role, policy limited to the bucket, 2 tables, 1 topic; creds only in `.env` (gitignored) |
| Bedrock | P2 | could act as a *non-controlled* second target; would not contain canaries — roadmap talking point only |
| Lambda, EventBridge Scheduler, Step Functions, API Gateway | P2 | scheduled re-probing and managed deployment are roadmap; no value inside a 4-minute live demo |
| CloudWatch | P2 | local logs suffice |
| QLDB | not used | AWS has ended support; replaced by hash chain + Object Lock |

Every AWS call is wrapped: timeout 5 s, one attempt, failure → component status `down`, demo continues.

---

## 18. Repository structure and ownership  *(`demo_site/` and `dashboard/` in the tree below do not exist on any ref; see §I.B.1)*

```
scapebusters/
├── Makefile, README.md, .env.example, .gitignore                     ANIRUDH
├── .github/CODEOWNERS, pull_request_template.md, workflows/check.yml (P1)   ANIRUDH
├── docs/plan/  (these six files), docs/DECISIONS.md, docs/INTEGRATION_LOG.md   ANIRUDH
├── contracts/schemas/*.schema.json   (generated)                       ANIRUDH
├── contracts/fixtures/*.json         (co-owned: shape by ANIRUDH, values by HARSH/HARDIK)
├── contracts/fixtures/scraped_dataset_sample.jsonl                     HARDIK
├── backend/requirements.txt, requirements-dev.txt                      ANIRUDH
├── backend/sb/main.py, config.py, contracts.py, hooks.py              ANIRUDH
├── backend/sb/store/                                                   ANIRUDH
├── backend/sb/edge/ (proxy, pipeline, context, session, layer1, layer2, intel, responses, static/, templates/)   ANIRUDH
├── backend/sb/trap/ (layer3, honeypots, decoys, injector)              HARDIK
├── backend/sb/canary/ (canaries.yaml, hashing, registry, seed)         HARDIK
├── backend/sb/provenance/ (dataset, rag, llm, doberman, correlate, evidence, vault_s3, alert)   HARDIK
├── backend/sb/api/health.py, traffic.py, sessions.py, overview.py     ANIRUDH
├── backend/sb/api/canaries.py, datasets.py, probes.py, cases.py       HARDIK
├── backend/sb/api/demo.py, backend/sb/demo/ (reset, runner, golden)   ARNAV
├── backend/tests/unit/<subsystem>/                                     subsystem owner
├── backend/tests/contract/                                             ANIRUDH
├── backend/tests/integration/                                          ANIRUDH (layer validation files: ARNAV)
├── backend/tests/e2e/                                                  ARNAV
├── demo_site/ (app.py, pages/*.html, static/site.css, robots.txt)           ARNAV
├── attacks/ (common, ordinary_bot, advanced_scraper, sophisticated_scraper, human_control)   ARNAV
├── data/control/, data/baseline/, data/replay/                         HARDIK
├── data/golden/                                                        ARNAV
├── data/datasets/, evidence/, backend/sb.db                            runtime, gitignored
├── scripts/export_schemas.py, check_contracts.py, check_ownership.py, dev.sh   ANIRUDH
├── scripts/preflight.py, smoke.sh                                      ARNAV
├── scripts/build_control_dataset.py                                    HARDIK
└── dashboard/                                                          HARSH
```

`scripts/stability.py` is owned by HARDIK.

**Make targets (Anirudh creates; owners fill):** `setup, up, backend, site, dashboard, test-unit, test-contract, test-integration, e2e, check, preflight, reset, demo, demo-step, capture-golden, restore-golden, smoke`.
`make check` = ruff + unit + contract + ownership report + `dashboard: npm run typecheck && npm run build`.

**Environment (`.env.example`, read only via `backend/sb/config.py`):** `SB_SECRET` (HMAC key for `sb_clear`), `SB_ORIGIN_URL=http://127.0.0.1:8001`, `SB_DB_PATH=backend/sb.db`, `SB_OLLAMA_URL=http://127.0.0.1:11434`, `SB_LLM_MODEL=qwen2.5:3b`, `SB_PROBE_CANARIES=` (comma list; empty = all), `SB_S3_BUCKET=`, `SB_SNS_TOPIC_ARN=`, `AWS_REGION=`. Empty AWS values = AWS features disabled.

**Git flow:** `main` protected (PR required, 1 approval from Anirudh, no force-push). Branches `feat/<person>/<topic>`, `fix/<person>/<topic>`, `int/<topic>`. Squash-merge. After each integration window that passes `make check && make test-integration`, Anirudh tags `kg-HNN` (known-good). Rollback = `git revert`, never history rewrite. Feature freeze tag `kg-freeze` (H24). Final tag `final` (H29).

---

## 19. Testing architecture

**Layers:** unit (pure functions, per owner) → contract (fixtures + live responses validate against `contracts.py`) → integration (FastAPI app + real origin, in-process, `httpx`) → E2E (real processes, real Playwright, real Ollama or fallback) → demo repeatability (reset + full run × N).

| ID | Area | Test | File / command | Owner | Gate |
|---|---|---|---|---|---|
| T-NU-1 | Normal user | `human_control.py` (headed, interacts, no hidden links, respects robots) passes L2, receives ≥ 5 content pages, **0 exposures**, classification HUMAN_LIKELY | `tests/e2e/test_normal_user.py` | Arnav | M3 |
| T-NU-2 | Normal user | live Chrome manual check on demo laptop | rehearsal checklist | Arnav | M9 |
| T-OB-1 | Ordinary bot | 100-request burst → first response THROTTLE, session BLOCKED before request 60, 0 origin pages (no "ExampleCorp Nimbus Platform" text in any body), reasons ⊇ {L1_AUTOMATION_UA} | `tests/integration/test_l1_ordinary_bot.py` | Arnav | M2 |
| T-OB-2 | L1 unit | table-driven scores for 10 header/UA/rate cases | `tests/unit/edge/test_layer1.py` | Anirudh | M2 |
| T-AS-1 | Advanced | headless Playwright → CHALLENGE then RESTRICT, reasons ⊇ {L2_WEBDRIVER, L2_HEADLESS_UA}, 0 origin pages | `tests/e2e/test_l2_advanced.py` | Arnav | M3 |
| T-AS-2 | L2 unit | PoW verify valid/invalid/expired; score bands; cookie HMAC bound to client_key | `tests/unit/edge/test_layer2.py` | Anirudh | M3 |
| T-SS-1 | Sophisticated | passes L2 (PASS event), hits TRAP-ROBOTS-01 or TRAP-LINK-01, TRAPPED, exposures for all 5 canaries, dataset file contains all 5 anchors, classification SOPHISTICATED_SCRAPER | `tests/e2e/test_l3_sophisticated.py` | Arnav | M4/M5 |
| T-CA-1 | Canary | hashing deterministic; registry round-trip; 5 canaries seeded ACTIVE with published_at | `tests/unit/canary/` | Hardik | M5 |
| T-CA-2 | Canary (neg) | no anchor appears in `demo_site/pages/**` or control dataset or baseline | `tests/unit/canary/test_uniqueness.py` | Hardik | M5 |
| T-CA-3 | Canary (neg) | no prompt contains its anchor or any context term | `tests/unit/canary/test_prompts.py` | Hardik | M6 |
| T-PR-1 | Probe | fixture dataset → Doberman persists 5 target + 5 control results with sha256 | `tests/unit/provenance/test_doberman.py` (LLM stubbed) | Hardik | M6 |
| T-PR-2 | Probe | Ollama down → mode `extractive_fallback`, run still completes | same file | Hardik | M6 |
| T-PR-3 | Probe stability | 10 live runs: each canary exact-matches ≥ 9/10; canaries below threshold are removed from `SB_PROBE_CANARIES` | `scripts/stability.py` (manual, H16) | Hardik | M7 |
| T-CO-1 | Correlation | positive fixture → DETECTED/HIGH | `tests/unit/provenance/test_correlate.py` | Hardik | M6 |
| T-CO-2 | Correlation (neg) | **clean control dataset → NO_SIGNAL for all canaries** | same | Hardik | M6 |
| T-CO-3 | Correlation (neg) | observed_at before published_at → INCONCLUSIVE; altered canary text → integrity INVALID; control positive → INCONCLUSIVE | same | Hardik | M6 |
| T-EV-1 | Evidence | bundle has all 10 files; manifest hashes match; chain links previous case | `tests/unit/provenance/test_evidence.py` | Hardik | M7 |
| T-EV-2 | Evidence (neg) | modify one byte in `06_model_response.json` → verify TAMPERED | same | Hardik | M7 |
| T-DB-1 | Dashboard | `npm run typecheck && npm run build`; mock mode renders all 6 routes without console errors | `dashboard/` | Harsh | M8 |
| T-DB-2 | Dashboard | live mode: fixtures and live payloads both parse (contract test for every GET) | `tests/contract/test_api_contracts.py` | Anirudh | M8 |
| T-E2E-1 | End-to-end | reset → run steps 1–7 → all PASS; case status DETECTED; verify VALID | `make e2e` → `tests/e2e/test_full_demo.py` | Arnav | M9 |
| T-RS-1 | Reset | reset twice → identical state: counts 0, 5 canaries ACTIVE, no sessions, edge state empty, new run_id | `tests/e2e/test_reset.py` | Arnav | M9 |
| T-RS-2 | Repeatability | 3 consecutive `make reset && make demo` PASS on demo laptop | manual log in `docs/INTEGRATION_LOG.md` | Arnav | M10 |
| T-NEG-1 | Negative | datasets harvested by scraper 1 and 2 (if any) contain 0 anchors | `tests/e2e/test_l2_advanced.py` | Arnav | M4 |
| T-NEG-2 | Negative | L2 decision unaffected by any client-supplied label header | `tests/unit/edge/test_layer2.py` | Anirudh | M3 |

---

## 20. Demo architecture  **[SUPERSEDED-v2: 15-step CampusCart E2E definition in §I.E; the 7 runner steps below map to it]**

`backend/sb/demo/runner.py` (Arnav) executes steps as subprocesses/API calls and **waits on observed API state, never on fixed sleeps** (poll every 0.5 s, per-step timeout).

| Step | Action | PASS condition (checked via API) | Timeout |
|---|---|---|---|
| 1 | `attacks/ordinary_bot.py` | a session with classification BOT_BASIC and state BLOCKED | 30 s |
| 2 | `attacks/advanced_scraper.py` | session AUTOMATION, state RESTRICTED | 60 s |
| 3 | `attacks/sophisticated_scraper.py --out data/datasets/<run>_scraper3.jsonl` | session SOPHISTICATED_SCRAPER, ≥ 5 exposures, dataset file exists | 120 s |
| 4 | ingest target (dataset) + control | 2 datasets registered | 20 s |
| 5 | `POST /api/v1/probes/run` | both probe runs DONE | 120 s |
| 6 | case check | latest case status PROVENANCE_SIGNAL_DETECTED | 10 s |
| 7 | `POST /cases/{id}/verify` | VALID | 10 s |

Modes: `make demo` (all steps), `make demo-step` (pauses for Enter between steps — used on stage), dashboard demo panel buttons call `POST /api/v1/demo/run {step}`.

---

## 21. Demo reset / recovery  *(amended for CampusCart in §I.F)*

**`RESET DEMO`** = `make reset` or `POST /api/v1/demo/reset` (Arnav's `demo/reset.py`), in order:
1. Refuse if a demo run holds the run lock (return 409).
2. `store.reset_db()` — drop/recreate all tables (Anirudh).
3. `edge_state.reset()` — rate windows, block list, pending challenges (Anirudh).
4. `trap_hooks.reset()` and `provenance.reset()` — trap state, BM25 indexes, ingested dataset cache (Hardik).
5. Delete `data/datasets/*.jsonl` and `data/datasets/ingested/*` (runtime only). **Evidence is never deleted**; new runs write under a new `run_id`.
6. New `run_id`, `demo_state.phase = READY`.
7. `canary.seed.seed_canaries()` — 5 ACTIVE canaries + publication records with fresh `published_at`.
8. Self-check: all counts 0, 5 ACTIVE canaries, origin reachable, LLM status reported → `{ok, run_id, checks}`.
Reset is idempotent. Browsers used by scrapers run in fresh contexts, so no client-side state carries over. The presenter's own Chrome must clear the `sb_clear` cookie (use a fresh Incognito window per rehearsal).

**Failure → fallback matrix**

| Failure | Detection | Fallback | Honest label on screen |
|---|---|---|---|
| Ollama down/slow | `/health` llm=down, 25 s timeout | extractive fallback mode | badge `FALLBACK` |
| Whole probe fails | step 5 FAIL | `make restore-golden` loads recorded golden run | banner `RECORDED RUN` |
| Playwright fails (scraper 2/3) | step FAIL | retry once; else restore golden | `RECORDED RUN` |
| AWS down | s3=down | evidence `PRESERVED_LOCAL` | badge `LOCAL ONLY` |
| Dashboard stale | last-updated > 3 s | manual refresh button; data persists in API | "last updated" timestamp |
| Laptop/process crash | — | `make up && make reset && make demo` (< 2 min); backup video (recorded H24) | video |

**Golden run** (`backend/sb/demo/golden.py`, Arnav): after the first fully passing run on the demo laptop (≥ H20), `make capture-golden` copies the SQLite DB (via `sqlite3` backup API), evidence folder and dataset to `data/golden/`. `restore-golden` restores them into a run with `mode: golden`.

---

## 22. 30-hour timeline  *(status of each milestone: §I.I; the hour-by-hour plan is historical)*

### 22.1 Milestones

| M | Name | Target | Verified by |
|---|---|---|---|
| M0 | Architecture + contracts locked (`contracts-v1` tag) | H2 | `make test-contract` green on main |
| M1 | First backend↔frontend handshake | H4 | dashboard live mode shows `/health` and real traffic events |
| M2 | Layer 1 working | H7 | T-OB-1, T-OB-2 |
| M3 | Layer 2 working | H10 | T-AS-1, T-AS-2, T-NU-1 |
| M4 | Layer 3 working | H12 | T-SS-1 (trap + exposures) |
| M5 | Canary pipeline working | H13 | T-CA-1/2 + exposures visible in dashboard |
| M6 | Probe working | H15 | T-PR-1/2, T-CO-1/2/3 on real scraped dataset |
| M7 | Evidence working | H17 | T-EV-1/2 |
| M8 | Dashboard connected (all 6 areas live) | H18 | T-DB-1/2 |
| M9 | **FIRST FULL END-TO-END DEMO** | **H20** | T-E2E-1 on demo laptop, tag `kg-M9` |
| M10 | Reliability lock | H25 | T-RS-2 (3 consecutive passes) |
| M11 | Presentation-ready | H28 | two full rehearsals incl. one failure drill |

### 22.2 Hour-by-hour (H0 = hackathon start; each row = one hour)

| H | Anirudh — INT | Hardik — CAN/PRV | Arnav — ATK/DEMO | Harsh — DSH | M |
|---|---|---|---|---|---|
| 0 | 30-min lock meeting (leads); INT-01 repo bootstrap; terminology diff | meeting; `ollama pull`; AWS creds check; CAN-01 start | meeting; install Playwright + Chromium; ATK-01 site | meeting; DSH-01 scaffold | |
| 1 | INT-02 contracts.py + fixtures v0 | CAN-01 hashing/registry/seed | ATK-01 pages + robots.txt | DSH-01 API client mock/live | |
| 2 | INT-03 store; tag `contracts-v1` | CAN-02 control/baseline/sample dataset | ATK-02 ordinary bot | DSH-02 shell + nav + status strip | **M0** |
| 3 | INT-04 edge proxy + pipeline + TrapHooks stub | PRV-01 BM25 RAG + ingest | ATK-03 advanced scraper | DSH-03 Overview ladder (mock) | |
| 4 | INT-05 health/traffic/sessions/overview APIs; merge window #1 | PRV-02 Ollama client + fallback | ATK-04 sophisticated scraper v0 | DSH-03 live `/health` + events | **M1** |
| 5 | INT-06 Layer 1 | PRV-03 Doberman (fixture dataset) | ATK-05 E2E harness + smoke | DSH-04 traffic feed + chart | |
| 6 | INT-06 throttle/block + tests; merge #2 | PRV-04 correlation + negatives | ATK-06a L1 validation | DSH-04 sessions + drawer | |
| 7 | INT-07 L2 interstitial + challenge.js | TRP-01 honeypots + decoys | ATK-06b human control | DSH-05 Canaries | **M2** |
| 8 | INT-07 PoW + verify + clearance; merge #3 | TRP-02 injector + exposures | ATK-06c L2 validation | DSH-06 Probe Center (mock) | |
| 9 | INT-07 tune bands vs scraper 2/human | TRP-02 TrapHooks PR | ATK-04 tune scraper 3 vs L2 | DSH-07 Cases list | |
| 10 | INT-08 intel classification; merge #4 | TRP-02 tests; canary API | ATK-06 M3 sign-off | DSH-07 Evidence detail (mock) | **M3** |
| 11 | integration tests L1–L3 | PRV-05 evidence bundle + chain | ATK-07 reset | DSH-08 demo panel | |
| 12 | merge #5 (trap); verify M4 | PRV-05 verify; PRV-06 cases API | ATK-06d L3 validation | DSH-09 live traffic/sessions | **M4** |
| 13 | INT-09 gates (check_contracts/ownership in `make check`) | M5 exposure check with live scraper 3 | ATK-08 runner steps 1–3 | DSH-09 live canaries | **M5** |
| 14 | overview aggregation live | PRV-06 datasets/ingest + probes API | ATK-08 runner steps 4–7 | DSH-09 error/empty states | |
| 15 | merge #6 (provenance) + integration | Doberman on real dataset + control | ATK-08 E2E full-chain test | DSH-09 live Probe Center | **M6** |
| 16 | integration fixes | PRV-07 stability (10 runs) | ATK-09 preflight | DSH-09 live Cases | |
| 17 | merge #7; tag `kg-H17` | M7; PRV-08 S3 Object Lock (P1) | ATK-10 golden capture/restore | DSH-09 live Evidence + Verify | **M7** |
| 18 | contract drift fixes; dashboard integration | PRV-08 receipts; replay data | T-E2E-1 green locally | all views live | **M8** |
| 19 | dry run #1 on demo laptop | fix probe issues | dry run #1 (drives) | dry run visual check | |
| 20 | **FULL E2E DEMO**; tag `kg-M9` | ← | ← capture golden | ← | **M9** |
| 21 | bug triage list; INT-11 DynamoDB only if green | fixes | fixes | **REST 90 min** | |
| 22 | fixes | PRV-09 SNS (P1) | **REST 90 min** | DSH-10 judge-comprehension pass | |
| 23 | fixes | **REST 90 min** | ATK-11 5× reset+run | DSH-10 projector pass | |
| 24 | **FEATURE FREEZE** `kg-freeze`; then **REST 90 min** | fixes (freeze rules) | record backup video | fixes | |
| 25 | reliability lock: 3 consecutive passes | ← | ← (runs) | ← | **M10** |
| 26 | demo laptop checked out at freeze tag | rehearse provenance segment | rehearse attack segment | rehearse dashboard walk | |
| 27 | **DEMO FREEZE** (critical fixes only) | rehearsal #1 | rehearsal #1 | rehearsal #1 | |
| 28 | rehearsal #2 + failure drill (kill Ollama; restore golden) | ← | ← | ← | **M11** |
| 29 | final: preflight → reset → full run → tag `final` | buffer | buffer | buffer | |

Rest windows are staggered so no two owners of the same interface are off together.

### 22.3 Task cards (every major task)

Format: WHAT · WHY · WHERE · WHO · DEPENDENCIES · TIME · TEST · HANDOFF. Priority in title.

**INT-01 · Repo bootstrap · P0**
- WHAT: create repo, directory tree (§18), Makefile targets (stubs), `.gitignore` (db, evidence, datasets, `.env`, node_modules), `.env.example`, CODEOWNERS, PR template, branch protection on main, `docs/DECISIONS.md` with A0–A6.
- WHY: every agent needs the skeleton and ownership rules before writing code.
- WHERE: repo root, `.github/`, `docs/`.
- WHO: Anirudh (agent generates, human sets GitHub protection).
- DEPS: none. TIME: 45 min (H0).
- TEST: `make help` lists targets; a direct push to main is rejected.
- HANDOFF: repo URL + "clone and branch" message to all.

**INT-02 · Shared contracts, fixtures, schema export · P0**
- WHAT: all §16 models in `backend/sb/contracts.py`; `scripts/export_schemas.py`; `scripts/check_contracts.py`; fixtures for every GET response (one realistic post-demo state).
- WHY: lets Harsh build on mocks and Hardik/Arnav integrate without waiting.
- WHERE: `backend/sb/contracts.py`, `contracts/schemas/`, `contracts/fixtures/`.
- WHO: Anirudh; Hardik reviews provenance models, Harsh reviews fixture usefulness.
- DEPS: INT-01. TIME: 90 min (H1–H2).
- TEST: `make test-contract` green.
- HANDOFF: tag `contracts-v1` = **M0**.

**INT-03 · SQLite store · P0**
- WHAT: `schema.sql` (§15), `db.py` (connect WAL, `execute/query` helpers with lock, `reset_db()`, JSON column helpers).
- WHY: single persistence layer for all subsystems; resettable.
- WHERE: `backend/sb/store/`. WHO: Anirudh. DEPS: INT-02. TIME: 45 min (H2).
- TEST: `tests/unit/store/test_db.py` (create, insert, reset empties all tables).
- HANDOFF: `from sb.store.db import db` usage note in PR.

**INT-04 · Edge proxy + pipeline skeleton · P0**
- WHAT: `main.py` app factory mounting catch-all edge route, `/_sb`, `/api/v1`; `context.py`; `session.py`; `proxy.py` (httpx); `pipeline.py` per §3 with L1/L2 returning ALLOW; event logging to `traffic_events`; `hooks.py` with no-op `TrapHooks` and reset-hook registry.
- WHY: the spine that every layer and the first vertical slice run through.
- WHERE: `backend/sb/main.py`, `backend/sb/edge/`, `backend/sb/hooks.py`. WHO: Anirudh. DEPS: INT-03, ATK-01 (origin). TIME: 75 min (H3).
- TEST: `tests/integration/test_proxy.py`: GET `/docs/` via edge returns origin HTML; event row written.
- HANDOFF: Hardik can implement `TrapHooks` against the stub.

**INT-05 · Control API: health, traffic, sessions, overview · P0**
- WHAT: `api/health.py`, `traffic.py` (`after` seq polling), `sessions.py`, `overview.py` (aggregates counts, ladder, pipeline stage status from table contents).
- WHY: first vertical slice website → edge → event → dashboard.
- WHERE: `backend/sb/api/`. WHO: Anirudh. DEPS: INT-04. TIME: 60 min (H4).
- TEST: contract tests validate live responses against models.
- HANDOFF: **M1** with Harsh (dashboard shows real events).

**INT-06 · Layer 1 engine · P0**
- WHAT: §4 rules, `EdgeState` (deques, block list, `reset()`), thresholds in config.
- WHY: stops Scraper 1 with zero client code.
- WHERE: `backend/sb/edge/layer1.py`, `config.py`. WHO: Anirudh (Arnav validates). DEPS: INT-04, ATK-02. TIME: 2 h (H5–H6).
- TEST: T-OB-1, T-OB-2.
- HANDOFF: **M2**; reason codes appear in feed.

**INT-07 · Layer 2 challenge · P0**
- WHAT: interstitial + `challenge.js` (signals, 1500 ms observation, pure-JS SHA-256 PoW 14 bits), `/_sb/verify`, score bands, `sb_clear` HMAC cookie, restricted page, `L2_NO_JS` rule.
- WHY: stops JS-capable crude automation; routes ambiguous clients to trap.
- WHERE: `backend/sb/edge/layer2.py`, `static/challenge.js`, `templates/`. WHO: Anirudh (Arnav validates). DEPS: INT-06, ATK-03. TIME: 3 h (H7–H9).
- TEST: T-AS-1, T-AS-2, T-NU-1, T-NEG-2.
- HANDOFF: **M3**; clearance semantics documented for Arnav's scraper 3.

**INT-08 · Scraper intelligence · P0**
- WHAT: §7 profile updates + classification in `intel.py`, `layer_path` append on each decision.
- WHY: dashboard and evidence need a per-scraper story.
- WHERE: `backend/sb/edge/intel.py`. WHO: Anirudh. DEPS: INT-07, TRP-02. TIME: 60 min (H10).
- TEST: `tests/unit/edge/test_intel.py` (4 synthetic paths → 4 classes).
- HANDOFF: `GET /api/v1/sessions/{id}` complete.

**INT-09 · Integration gates · P0**
- WHAT: `check_ownership.py` (lists files changed outside the author's owned paths from CODEOWNERS; warning in PR), `check_contracts.py` in `make check`, PR template checklist, `docs/INTEGRATION_LOG.md`.
- WHY: agents on 4 machines will drift; gates catch it before main.
- WHERE: `scripts/`, `Makefile`. WHO: Anirudh. DEPS: INT-02. TIME: 60 min (H13).
- TEST: a PR touching another owner's file shows the warning.
- HANDOFF: rule announced: no merge without `make check` output pasted in PR.

**INT-10 · Continuous integration windows · P0 (ongoing)**
- WHAT: merge windows at H4, H6, H8, H10, H12, H15, H17, then continuous; each: pull PRs in dependency order, `make check`, `make test-integration`, squash-merge, tag `kg-HNN`, log in INTEGRATION_LOG.
- WHY: avoids big-bang merge at H25.
- WHERE: GitHub + `docs/INTEGRATION_LOG.md`. WHO: Anirudh (human decides merges). DEPS: all. TIME: ~20 min per window.
- TEST: main always passes `make check`.
- HANDOFF: tag announced in team chat.

**INT-11 · DynamoDB mirror · P1-low**
- WHAT: write-through of canaries and cases to `sb_canaries`, `sb_cases` (best-effort, 5 s timeout).
- WHY: AWS metadata story. WHERE: `backend/sb/store/dynamo_mirror.py`. WHO: Anirudh. DEPS: M9 green. TIME: 60 min (H21). TEST: item visible via `aws dynamodb get-item`; AWS disabled → no errors. HANDOFF: health component.

**INT-12 · Release · P0**
- WHAT: freeze at H24, demo freeze at H27, final tag H29; demo laptop runs exactly the tagged commit.
- WHY: no late regressions on stage. WHO: Anirudh. TIME: spread. TEST: T-RS-2 on the tagged commit. HANDOFF: `final` tag + commit hash posted.

**CAN-01 · Canary registry, hashing, seed · P0**
- WHAT: `canaries.yaml` (§8 table verbatim), `hashing.py` (normalize, canonical hash, block hash), `registry.py` (CRUD over `canaries`, `publications`, `exposures`, status transitions), `seed.py`.
- WHY: every downstream signal depends on stable, hashed canaries.
- WHERE: `backend/sb/canary/`. WHO: Hardik. DEPS: INT-02 (models), INT-03 (store; until then use an in-memory fake). TIME: 90 min (H0–H1).
- TEST: T-CA-1, T-CA-3.
- HANDOFF: `registry.record_exposure(...)` API for the injector; canary fixture values to Harsh.

**CAN-02 · Control, baseline, sample dataset · P0**
- WHAT: `scripts/build_control_dataset.py`, `data/control/control_clean.jsonl`, `data/baseline/public_baseline.jsonl`, `contracts/fixtures/scraped_dataset_sample.jsonl` (8 pages, 5 with canary paragraphs).
- WHY: decouples provenance work from the scraper; enables negative tests.
- WHERE: as listed. WHO: Hardik. DEPS: ATK-01 pages (control); none for sample. TIME: 60 min (H2).
- TEST: T-CA-2. HANDOFF: dataset JSONL contract confirmed with Arnav.

**PRV-01 · RAG index + ingest · P0**
- WHAT: `dataset.py` (validate JSONL, sha256, register), `rag.py` (paragraph chunking, BM25, `retrieve(q, k=3)`), per-dataset index cache, `reset()`.
- WHERE: `backend/sb/provenance/`. WHO: Hardik. DEPS: CAN-02. TIME: 60 min (H3).
- TEST: canary question retrieves its canary chunk top-1 on sample dataset. HANDOFF: used by Doberman.

**PRV-02 · LLM client · P0**
- WHAT: `llm.py` Ollama generate (options §9, 25 s timeout), `model_info()` (name+digest), extractive fallback, replay loader.
- WHERE: `backend/sb/provenance/llm.py`. WHO: Hardik. DEPS: model pulled. TIME: 60 min (H4).
- TEST: T-PR-2. HANDOFF: `/health` llm component value.

**PRV-03 · Doberman · P0**
- WHAT: §10 loop over target and control, persistence to `probe_runs`/`probe_results`.
- WHERE: `backend/sb/provenance/doberman.py`. WHO: Hardik. DEPS: PRV-01/02, CAN-01. TIME: 60 min (H5). TEST: T-PR-1. HANDOFF: probe ids to correlate.

**PRV-04 · Correlation · P0**
- WHAT: §11 signals, status, confidence, statement text.
- WHERE: `backend/sb/provenance/correlate.py`. WHO: Hardik. DEPS: PRV-03. TIME: 60 min (H6). TEST: T-CO-1/2/3. HANDOFF: findings to evidence.

**TRP-01 · Honeypots + decoys · P0**
- WHAT: `honeypots.py` (trap registry §6), `decoys.py` (`/internal/`, `/docs/archive/legacy-index`, decoy JSON API), `layer3.classify_request`.
- WHERE: `backend/sb/trap/`. WHO: Hardik. DEPS: INT-04 stub. TIME: 60 min (H7).
- TEST: `tests/unit/trap/test_layer3.py`: each trap path → TrapHit with correct trap_id; normal doc path → None.
- HANDOFF: robots line `Disallow: /internal/` confirmed in Arnav's robots.txt.

**TRP-02 · Injector, exposures, TrapHooks implementation · P0**
- WHAT: `injector.transform_response` (hidden link on all HTML; canary paragraph before `</main>` for TRAPPED sessions on placement pages; decoy API JSON), exposure recording, `TrapHooks` registration in app startup (one-line PR to `main.py`, reviewed by Anirudh).
- WHERE: `backend/sb/trap/injector.py`, `layer3.py`. WHO: Hardik. DEPS: TRP-01, CAN-01, INT-04. TIME: 2 h (H8–H9).
- TEST: `tests/integration/test_trap_injection.py`: TRAPPED session gets canary on `/docs/architecture` + exposure row; VERIFIED session gets hidden link but **no canary**.
- HANDOFF: **M4** with Arnav's T-SS-1.

**PRV-05 · Evidence bundle + verify · P0**
- WHAT: §12 files, manifest, chain, chmod, `verify_case()`.
- WHERE: `backend/sb/provenance/evidence.py`. WHO: Hardik. DEPS: PRV-04. TIME: 2 h (H11–H12). TEST: T-EV-1/2. HANDOFF: **M7**.

**PRV-06 · Provenance APIs · P0**
- WHAT: `api/canaries.py`, `datasets.py`, `probes.py`, `cases.py` per §16.
- WHERE: `backend/sb/api/`. WHO: Hardik. DEPS: PRV-01…05, INT-02. TIME: 2 h (H12–H15).
- TEST: contract tests pass against live responses. HANDOFF: Harsh switches views to live.

**PRV-07 · Stability + replay data · P0**
- WHAT: `scripts/stability.py` (10 runs), prune flaky canaries via `SB_PROBE_CANARIES`, save one full set of responses to `data/replay/`.
- WHO: Hardik. DEPS: M6. TIME: 60 min (H16). TEST: T-PR-3. HANDOFF: stability numbers in INTEGRATION_LOG.

**PRV-08 · S3 Object Lock vault · P1-high**
- WHAT: `vault_s3.py` upload after bundle creation; `vault_receipt.json`; `/health` s3.
- WHO: Hardik. DEPS: PRV-05, AWS creds. TIME: 90 min (H17–H18).
- TEST: `aws s3api get-object-retention` shows GOVERNANCE + date; AWS unset → `PRESERVED_LOCAL`, no exception. HANDOFF: receipt in Evidence view.

**PRV-09 · SNS alert · P1-low** — WHAT: publish case summary on DETECTED. WHERE: `provenance/alert.py`. WHO: Hardik. TIME: 30 min (H22). TEST: email received; disabled → no-op.

**ATK-01 · ExampleCorp origin site · P0 — [SUPERSEDED-v2: CANCELLED; CampusCart is the target (§I.A C1)]**
- WHAT: `demo_site/app.py` + 8 synthetic pages (§13) with realistic docs prose, one `<main id="content">`, nav links, `robots.txt` with `Disallow: /internal/`.
- WHY: the thing being protected. WHERE: `demo_site/`. WHO: Arnav. DEPS: none. TIME: 90 min (H0–H1).
- TEST: `curl :8001/docs/api` 200; grep shows no canary anchors. HANDOFF: origin URL to Anirudh.

**ATK-02 · Scraper 1 — ordinary bot · P0**
- WHAT: `attacks/ordinary_bot.py`: `requests` default UA, 10 threads, 100 GETs over the page list, no cookies; prints per-status counts; exit 0.
- WHERE: `attacks/`. WHO: Arnav. DEPS: INT-04. TIME: 30 min (H2). TEST: T-OB-1. HANDOFF: validation of INT-06.

**ATK-03 · Scraper 2 — advanced automation · P0**
- WHAT: `advanced_scraper.py`: Playwright Chromium `headless=True`, default UA, `locale="en-US"`, waits for navigation, visits 6 pages at 1 page/s, no interaction, no stealth patches.
- WHO: Arnav. DEPS: INT-04. TIME: 45 min (H3). TEST: T-AS-1. HANDOFF: validation of INT-07.

**ATK-04 · Scraper 3 — sophisticated scraper · P0**
- WHAT: `sophisticated_scraper.py`: Playwright Chromium **headed** (fallback: headless with patches), `--disable-blink-features=AutomationControlled`, init script sets `navigator.webdriver` undefined, realistic UA + headers, synthetic mouse moves/scrolls during the 1.5 s challenge window, 1 page per 2–3 s; order: `/` → read `robots.txt` → fetch disallowed paths → BFS over **all** `<a href>` including hidden; ignores robots; writes dataset JSONL (§9 contract) with `innerText` of `<main>` (or body for decoys).
- WHO: Arnav. DEPS: INT-07, TRP-02. TIME: 60 min (H4) + 60 min tuning (H9).
- TEST: T-SS-1. HANDOFF: dataset path to Hardik; **M4/M5**.

**ATK-05 · E2E harness + smoke · P0**
- WHAT: pytest fixture starting backend + site via subprocess on test ports, waits for `/health`; `scripts/smoke.sh` (health, one page through edge, dashboard build).
- WHO: Arnav. DEPS: INT-04. TIME: 60 min (H5). TEST: `make smoke` green. HANDOFF: used by all e2e tests.

**ATK-06 · Layer validation suites + human control · P0**
- WHAT: T-OB-1 (H6), `human_control.py` + T-NU-1 (H7), T-AS-1 (H8), T-SS-1 + T-NEG-1 (H12). Failures are reported to the layer owner with the exact event rows; Arnav does **not** fix edge code.
- WHO: Arnav. DEPS: INT-06/07, TRP-02. TIME: 4 × 45 min. HANDOFF: sign-off on M2, M3, M4.

**ATK-07 · Reset · P0**
- WHAT: §21 procedure in `backend/sb/demo/reset.py`, `POST /api/v1/demo/reset`, `make reset`.
- WHO: Arnav. DEPS: reset hooks from INT-03/INT-06/TRP-02/PRV-01. TIME: 60 min (H11). TEST: T-RS-1. HANDOFF: dashboard "Reset" button.

**ATK-08 · Demo runner · P0**
- WHAT: §20 steps, run lock, `DemoStatus` persistence, `/api/v1/demo/run`, `/status`, `make demo`, `make demo-step`.
- WHO: Arnav. DEPS: ATK-02/03/04, PRV-06. TIME: 2 h (H13–H14) + E2E test (H15). TEST: T-E2E-1. HANDOFF: **M9**.

**ATK-09 · Preflight · P0**
- WHAT: `scripts/preflight.py`: ports free/used as expected, Python/Node versions, Ollama reachable + model present, Playwright Chromium installed, DB writable, disk space, AWS optional check, dashboard reachable; prints PASS/WARN/FAIL table.
- WHO: Arnav. TIME: 45 min (H16). TEST: kill Ollama → FAIL line for llm, exit code 1. HANDOFF: first command of every rehearsal.

**ATK-10 · Golden run · P0**
- WHAT: `backend/sb/demo/golden.py` capture/restore, `make capture-golden`, `make restore-golden`, dashboard banner flag `mode: golden`.
- WHO: Arnav. TIME: 60 min (H17). TEST: restore on clean state → dashboard shows full case with `RECORDED RUN`. HANDOFF: fallback drill at H28.

**ATK-11 · Repeatability + backup video · P0**
- WHAT: 5× reset+run log; screen recording of a full passing run.
- WHO: Arnav. TIME: H23–H24. TEST: T-RS-2. HANDOFF: video file on 2 laptops + USB.

**DSH-01 · Scaffold + API client · P0** — WHAT: Vite React TS, Tailwind, Recharts, router; `src/api/client.ts` (live), `src/api/mock.ts` (imports `../../contracts/fixtures/*.json`), `src/types/contracts.ts` mirroring §16. WHO: Harsh. DEPS: INT-02 fixtures (use drafts until M0). TIME: 2 h (H0–H1). TEST: T-DB-1. HANDOFF: none.

**DSH-02 · Shell · P0** — WHAT: sidebar with 6 areas, top status strip (run_id, health badges, last-updated). TIME: 60 min (H2). TEST: routes render.

**DSH-03 · Overview · P0** — WHAT: defense ladder 6 stages with counts + highlight of current demo stage, pipeline strip, latest case card. TIME: 2 h (H3–H4). TEST: mock + live. HANDOFF: **M1** with Anirudh.

**DSH-04 · Traffic / Scrapers · P0** — WHAT: event feed (incremental `after=seq`), decisions-over-time stacked bar (Recharts, 10 s buckets), sessions table, session drawer. TIME: 2 h (H5–H6).

**DSH-05 · Canaries · P0** — TIME: 60 min (H7). **DSH-06 · Probe Center · P0** — highlight anchor/context terms in responses, mode badge. TIME: 60 min (H8). **DSH-07 · Cases + Evidence detail · P0** — §11.3 block, timeline, statement, manifest, Verify. TIME: 2 h (H9–H10). **DSH-08 · Demo panel · P0** — step list with status, Reset / Run step / Run all buttons, golden banner. TIME: 60 min (H11).

**DSH-09 · Live integration · P0** — WHAT: switch each area to live as its API lands (H12–H18), error/empty/API-down states. TEST: T-DB-2 + visual check during dry run. HANDOFF: **M8**.

**DSH-10 · Judge/projector pass · P0** — WHAT: plain-language labels ("Blocked at Layer 1: automation client, burst rate"), legend for the ladder, 1280×720 layout check, remove anything not used in the demo. TIME: 2 h (H22–H23).

---

## 23. Critical path

```
M0 contracts (H2) → INT-04 edge skeleton (H3) → INT-06 L1 (H6) → INT-07 L2 (H9)
   → TRP-02 trap injection (H9–H10) → ATK-04 scraper 3 passes L2 & harvests canaries (H9–H12)
   → real dataset → PRV-06 ingest/probe on real data (H14–H15) → PRV-05 evidence (H12/H17)
   → ATK-08 runner (H14–H15) → DSH-09 evidence view live (H17) → M9 (H20)
```
Highest-risk links: **(1)** scraper 3 must pass L2 while scraper 2 must fail — tuned jointly by Anirudh and Arnav at H9; **(2)** small local model must reproduce anchors reliably — measured at H16 (PRV-07).
Off the critical path by design: the whole provenance pipeline (built H3–H6 against the sample dataset), the whole dashboard (built against fixtures), AWS.

---

## 24. Parallel work

| Stream | Can run in parallel because | Joins at |
|---|---|---|
| Edge (Anirudh) | owns `edge/`, `store/`, TrapHooks stub | H9 (TrapHooks), H12 (M4) |
| Provenance (Hardik) | sample dataset fixture replaces the scraper until H13 | H13 (real dataset) |
| Attacks/site (Arnav) | site first, scripts only need the origin + edge skeleton | H6/H8/H12 validations |
| Dashboard (Harsh) | fixtures replace APIs until H12 | H4 (M1), H12–H18 |

Exclusive file ownership (§18) prevents agents from colliding; cross-owner edits go through the owner as a PR request.

---

## 25. Scope priorities

| Feature | P |
|---|---|
| Reverse-proxy edge, origin site, event log, SQLite | P0 |
| L1 rules (UA, headers, HTTP fingerprint, rate, block) | P0 |
| L2 interstitial, JS signals, PoW, clearance cookie, bands | P0 |
| L3 hidden link, robots decoy, decoy API, deception injection, exposures | P0 |
| 5 canaries, registry, hashing, publication records | P0 |
| Scraper intelligence + classification | P0 |
| Controlled dataset, BM25 RAG, Ollama, extractive fallback | P0 |
| Doberman target + control probes | P0 |
| Correlation (exact, context, uniqueness, temporal, integrity, control) | P0 |
| Evidence bundle, manifest, hash chain, verify | P0 |
| Dashboard 6 areas + demo panel | P0 |
| 3 scrapers + human control, runner, reset, preflight, golden restore, E2E | P0 |
| S3 Object Lock upload + receipt | P1-high |
| Tamper demo button (edit file → TAMPERED) in UI | P1 |
| SSE live stream instead of polling | P1 |
| Second prompt per canary | P1 |
| DynamoDB mirror, SNS alert, admin token on `/api` | P1-low |
| Passive L2 beacon mode, Docker Compose, GitHub Actions | P1-low |
| Per-session unique canary variants | P2 |
| JA3/JA4 TLS fingerprint, Bedrock/commercial probing, Lambda/Step Functions scheduled probing, CloudWatch, in-process ASGI middleware variant, multi-site | P2 |

---

## 26. Risk register

| # | Risk | L | I | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Scraper 3 fails L2 non-deterministically | M | H | headed browser + disable AutomationControlled; tune weights at H9 with printed signal dumps; TRAP band 40–69 still traps it | Arnav + Anirudh |
| R2 | Scraper 2 accidentally passes L2 | L | H | webdriver+HeadlessChrome already = 90; T-AS-1 gate | Arnav |
| R3 | Local model paraphrases away the anchor | M | H | temperature 0, retrieval top-3, stability test, prune flaky canaries, extractive fallback | Hardik |
| R4 | Model too slow on stage | M | M | `num_predict` 96, limit to 3 canaries, pre-warm model in preflight | Hardik |
| R5 | Contract drift between agents | H | M | pydantic single source, fixtures validated, `contract-change` label | Anirudh |
| R6 | Late big-bang merge | M | H | fixed merge windows, `kg` tags | Anirudh |
| R7 | Agent edits another owner's files | H | M | CODEOWNERS, `check_ownership.py`, prompt rules | Anirudh |
| R8 | Normal user receives canaries (credibility) | L | H | injector only for TRAPPED; T-NU-1 gate | Hardik |
| R9 | False positive on control | L | H | anchors unusual; T-CA-2, T-CO-2 | Hardik |
| R10 | Venue Wi-Fi/AWS down | M | L | everything local; AWS best-effort | All |
| R11 | Demo laptop environment differs | M | H | demo laptop chosen H0, dry run H19, preflight | Arnav |
| R12 | Overclaiming in pitch | M | H | §11.4 statement on screen and in script | Hardik |
| R13 | Fatigue errors after H20 | H | M | staggered rest, freeze H24, demo freeze H27 | Anirudh |
| R14 | Presenter Chrome has stale clearance cookie | M | L | fresh Incognito window per run | Arnav |

---

## 27. Definition of Done  *(amended: read "origin site" as CampusCart, and require live dashboard data per §I.D.3)*

**Per task:** code on a feature branch; owner's tests pass and output is pasted into the PR; `make check` green; no files outside ownership changed (or explicitly approved); PR describes changed files, tests run, what was not verified.
**Per milestone:** the milestone's tests in §22.1 pass on `main` after merge; tag created.
**Project (all must be true on the `final` tag, on the demo laptop):**
1. `make preflight` → no FAIL.
2. `make reset` → 5 ACTIVE canaries, zero traffic, new run_id.
3. Human in Chrome browses 3 pages → SAFE, 0 exposures.
4. Scraper 1 → BLOCKED at L1 with reasons shown.
5. Scraper 2 → RESTRICTED at L2 with signals shown.
6. Scraper 3 → PASS L2 → TRAP → 5 exposures → SOPHISTICATED_SCRAPER profile.
7. Doberman probes target + control; target reproduces ≥ 3 anchors; control reproduces 0.
8. Case SB-001 status PROVENANCE_SIGNAL_DETECTED with statement §11.4.
9. Evidence bundle present, verify VALID; tamper test shows TAMPERED (P0 via test, P1 via UI).
10. Dashboard shows every step live on all six areas.
11. Three consecutive `make reset && make demo` passes logged.
12. Golden restore and backup video both verified.
13. No canary text in origin site or control dataset; no AWS credentials in the repo.


---

# PART III — OPEN PR / MERGE QUEUE AND NEXT AGENT GOALS

> Audit-time facts: `main` = `4b1f0ea`. PR open/closed state, reviews, CI/checks and base branches could **not** be read (GitHub API not accessible from the audit environment). "Not in `main`" below means the PR head is not an ancestor of `main`; whether the PR is still open is `NOT VERIFIED`. All three merge cleanly against `main` (`git merge-tree --write-tree`). **No PR was merged, modified or closed by this audit.**

# OPEN PR / MERGE QUEUE

Merged into `main` (for reference, no action): #1 INT-05 control API · #2 attacks/demo/e2e harness (Arnav) · #3 canary + provenance + trap (Hardik) · #4 TrapHooks registration · #5 Jules smoke-test note · #6 Ruff fixes (Arnav) · #9 Jules review timeout (Arnav).

**PR #7**

- OWNER: Hardik (git author `Hardhik Bhatia`)
- BRANCH: `feat/hardik/s3-vault` (head `e330db1`)
- TARGET: `main` (assumed; base NOT VERIFIED)
- PURPOSE: PRV-08 S3 Object Lock vault — GOVERNANCE 24 h, SHA256 checksums, background single-attempt upload, `vault_receipt.json`; replaces the `s3_status()` stub.
- REVIEW: NOT VERIFIED
- CI: NOT VERIFIED (only the Jules AI-review workflow exists; no test workflow)
- DEPENDENCIES: none on other open PRs. PR #10 is stacked on it (contains its commits). `boto3` not in `requirements.txt` (F-09).
- SAFE TO MERGE: Not verified. Conflict-free vs `main`; no AWS run was performed; its real-botocore test is skipped without `boto3`. Suggested handling: merge **before** #10, or skip #7 and merge only #10 (which already contains #7's commits) — operator's choice.
- BLOCKER: review status unknown; `boto3` dependency; AWS untested (operator config).
- NEXT ACTION: reviewer confirms; then merge #7 → #10 (or #10 alone); add `boto3` to requirements (R-13/R-14).

**PR #8**

- OWNER: Arnav (git author `Kashyep`)
- BRANCH: `feat/arnav/campuscart-origin` (head `b1ea3b0`)
- TARGET: `main` (assumed; NOT VERIFIED)
- PURPOSE: CampusCart integration — `UPSTREAM_ORIGIN` (default `https://campuscart-c73de.web.app`), Host rewrite, identity encoding, edge `robots.txt` lure, `TRAP-ROBOTS-01` inject-all-canaries, attacks' CampusCart site profile, preflight/smoke, scraper-3 dataset kept out of git.
- REVIEW: NOT VERIFIED
- CI: NOT VERIFIED; auditor ran unit+contract+integration on the head snapshot: 150 passed, 2 skipped, 2 xfailed. e2e and any attack against CampusCart NOT run.
- DEPENDENCIES: none blocking; independent of #7/#10 (disjoint files). Edits cross-owner files: `sb/trap/injector.py` (Hardik), `sb/edge/proxy.py` and `sb/config.py` (Ani) — `check_ownership.py` would warn.
- SAFE TO MERGE: Not verified — conflict-free and tests pass on the snapshot, but requires Ani and Hardik review of their files; default origin in `main` becomes the live CampusCart URL (affects every local run and test that relies on `SB_ORIGIN_URL` defaults).
- BLOCKER: cross-owner review; decision OD-3/OD-4 affects the injector change.
- NEXT ACTION: Ani reviews `proxy.py`/`config.py`; Hardik reviews `injector.py`; then merge (R-06); follow with R-07 (retarget e2e).

**PR #10**

- OWNER: Hardik (git author `Hardhik Bhatia`)
- BRANCH: `fix/vault-s3-receipt-db-failure` (head `7c2ff52` at audit time; it was `ffacc3b` earlier the same session)
- TARGET: `main` (assumed; NOT VERIFIED — may target `feat/hardik/s3-vault`)
- PURPOSE: hardening of the S3 vault — handle receipt/DB failures after upload, document and test single-attempt retry config against real botocore; wires `vault_s3.preserve_async` into `investigate`; removes the old `s3_status` stub test.
- REVIEW: NOT VERIFIED
- CI: NOT VERIFIED; snapshot tests: 154 passed, 3 skipped (real-botocore test skipped), 2 xfailed. `refs/pull/10/merge` exists on the remote (GitHub-computed merge ref, suggests it is open and mergeable — inference only).
- DEPENDENCIES: **stacked on PR #7** (contains its 3 commits). Merge #7 first, or merge #10 alone.
- SAFE TO MERGE: Not verified — branch is still moving (head changed during this audit); wait for it to settle.
- BLOCKER: head still changing; `boto3` dependency; no AWS verification.
- NEXT ACTION: Hardik confirms the head is final; then merge after #7 (or alone), then R-13/R-14.

**Suggested merge order (operator decides):** #8 (after the two cross-owner reviews) and #7 → #10 are independent of each other; neither unblocks the critical path items R-01…R-04, which need **new** PRs from Ani.

# NEXT AGENT GOALS

## ARNAV NEXT GOAL

**One objective: make the attack/demo side run against CampusCart safely and be ready to execute the live E2E the moment the backend blockers clear.**

- **Files likely involved:** `attacks/common.py`, `attacks/*.py` (SD-1/SD-2/SD-4 guard, marked test UA), `backend/tests/e2e/conftest.py` and e2e scenario tests (retarget to the CampusCart site profile), `Makefile` (demo targets only: `e2e preflight demo demo-step capture-golden restore-golden smoke`, and `reset` → demo reset).
- **Dependency:** PR #8 reviewed and merged (Ani, Hardik) — start on top of it; the live run itself additionally needs Ani's R-01…R-04 and Hardik's control dataset (R-11). Work that does not need them (guards, test retargeting, Makefile recipes) can proceed now.
- **Acceptance test:** (1) an attack with a non-loopback `--base` exits non-zero without an explicit override; (2) `make preflight` prints a PASS/WARN/FAIL table and exits 1 when Ollama or the CampusCart upstream is down; (3) `pytest backend/tests/e2e --collect-only` shows no hard-coded ExampleCorp expectations except a labelled local fixture; (4) when the blockers clear: `make e2e` green, output pasted in the PR.
- **What NOT to touch:** `backend/sb/edge/*`, `backend/sb/main.py`, `backend/sb/trap/*`, `backend/sb/provenance/*`, `backend/sb/canary/*`, `contracts.py`. Do not attack anything except the local edge; do not merge PRs.

## HARDIK NEXT GOAL

**One objective: produce the real-data provenance inputs for CampusCart — canary decision, control dataset, and a stability-checked run — while landing the S3 vault PRs.**

- **Files likely involved:** `docs/DECISIONS.md` (OD-3/OD-4 record), `backend/sb/canary/canaries.yaml`, `backend/sb/trap/decoys.py` (only if re-theming), `scripts/build_control_dataset.py`, `data/control/control_clean.jsonl`, `scripts/stability.py`, `docs/INTEGRATION_LOG.md`, `backend/requirements.txt` coordination with Ani for `boto3`; PR #7/#10 finalisation.
- **Dependency:** OD-3/OD-4 decision with Arnav (first); a real scraper-3 dataset needs PR #8, R-01…R-04 (Ani) — the control dataset and canary work do **not** wait for them. AWS setup is the operator's.
- **Acceptance test:** (1) decision recorded and `pytest backend/tests/unit/canary backend/tests/unit/trap` passes with T-CA-2 **not skipped** against CampusCart content; (2) `data/control/control_clean.jsonl` exists and contains none of the 5 anchors; (3) `SB-CAN-0004` xfail resolved or explicitly re-justified; (4) once the dataset exists: stability numbers (≥ 9/10 exact match per canary, or canary pruned) recorded in `docs/INTEGRATION_LOG.md`; (5) PR #10 head declared final and PR #7/#10 merged in order with test output pasted.
- **What NOT to touch:** `backend/sb/edge/*`, `backend/sb/main.py`, `attacks/*`, `backend/sb/demo/*`, `contracts.py` (request changes from Ani). No credentials in the repo; do not configure AWS accounts.

## ANI NEXT GOAL

**One objective: make the backend actually serve real, persisted attack telemetry and the full API so the dashboard and the E2E can run — R-01 → R-04, in that order.**

- **Files likely involved:** `backend/sb/main.py` (mount routers), `backend/sb/edge/layer1.py`, `edge/layer2.py`, `edge/static/challenge.js`, `edge/pipeline.py`, `edge/session.py`, `edge/intel.py`, `backend/sb/api/{health,overview,sessions,traffic}.py`, `backend/sb/store/schema.sql`, `backend/tests/{unit/edge,integration,contract}`, `docs/DECISIONS.md` (close OD-1/OD-2).
- **Dependency:** none for R-01; R-02/R-03 need the OD-1/OD-2 decisions (recommended: conform code to `§4`/`§5`); reviewing PR #8's `proxy.py`/`config.py` is a parallel task (R-06). Provenance response models come from Hardik.
- **Acceptance test:** (1) every URL in `§I.D.2` returns JSON, not proxied HTML; (2) `test_l1_ordinary_bot` unxfailed and passing (100-request burst → BLOCK before request 60, 0 origin bodies); (3) after a scripted run `GET /traffic/events` returns only contract-legal rows for L1/L2/L3, `GET /sessions/{id}` returns DB-backed fields, `GET /overview` counts equal SQL counts; (4) `pytest backend/tests/unit backend/tests/contract backend/tests/integration` output pasted, no new xfail.
- **What NOT to touch:** `backend/sb/trap/*`, `backend/sb/canary/*`, `backend/sb/provenance/*`, `attacks/*`, `backend/sb/demo/*` (owners' files). Do not merge PRs or change the Part I plan beyond status updates.
