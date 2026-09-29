# SCAPEBUSTERS — Master Implementation Plan

**Version:** 1.0 (canonical) · **Event:** 30-hour hackathon · **Type:** proof-of-concept, single protected website
**Rule:** ONE architecture · ONE master plan · FOUR scoped execution prompts · ONE integration process · ONE deterministic demo.
This file is the source of truth. Individual prompts reference sections here as `§N`.

---

## 0. Read this first

### 0.1 Source status and explicit assumptions

| ID | Assumption / decision | Consequence | Who confirms at H0 |
|---|---|---|---|
| A0 | The four source documents (deck, pitch script, one-pager, whitepaper) were **not attached** to the planning request. This plan is built from the canonical direction brief, which the brief itself declares final where documents differ. | Terminology used here: ScapeBusters, Layer 1/2/3, canary, Doberman (interrogator), Provenance Finding, Provenance Case. **H0 task:** Anirudh spends 15 min diffing names and claims in the deck/pitch script against this plan; any change is recorded in `docs/DECISIONS.md`. | Anirudh |
| A1 | **Ownership gap:** the role brief assigns no builder for the edge proxy, Layer 1 and Layer 2, or the demo website. | Options: (a) Anirudh's agent builds the edge spine (proxy, L1, L2, store) — he already owns contracts and the integration point; builder ≠ validator because Arnav attacks it. (b) Arnav builds L1/L2 — fastest feedback, but the builder grades his own work. (c) Split L1→Anirudh, L2→Hardik — overloads the critical-path owner. **Chosen: (a).** The demo website (synthetic content only) goes to Arnav as part of the demo environment. | All four |
| A2 | Product name: brief uses "ScapeBusters"; pitch docs use "ScrapeBuster". | Code prefix `sb`, UI title "ScapeBusters". Decide the spoken name at H0. | Team |
| A3 | Demo runs on **one designated demo laptop**, fully offline-capable (local model, local storage). | AWS is a best-effort enhancement layer, never on the critical path. | Team picks the laptop with most RAM/GPU at H0 |
| A4 | AWS account + credentials exist. If judging explicitly rewards AWS usage, promote PRV-08 (S3 Object Lock) to P0 — still with local fallback. | No change to critical path. | Hardik (`aws sts get-caller-identity` at H0) |
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

## 2. Final architecture

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

## 3. Runtime request decision flow

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

## 4. Layer 1 — Passive edge defense

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

## 5. Layer 2 — Behavioral / automation verification

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

## 8. Canary system

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

## 13. Website integration

- ExampleCorp origin (`demo_site/app.py`, Arnav) is a tiny FastAPI static server on :8001 with 8 pages: `/`, `/docs/`, `/docs/getting-started`, `/docs/architecture`, `/docs/api`, `/docs/team`, `/docs/operations`, `/docs/metrics`, plus `/pricing`, `robots.txt`, `/static/site.css`. Each page has exactly one `<main id="content">…</main>`. **No canary text exists in origin files** (tested).
- The origin knows nothing about ScapeBusters. Integration = pointing traffic at the edge (`SB_ORIGIN_URL=http://127.0.0.1:8001`). This is the "reverse-proxy integration method"; an in-process ASGI middleware variant is P2.
- The edge forwards method, path, query, body and safe headers via `httpx.AsyncClient`; strips hop-by-hop headers; rewrites nothing except HTML/JSON bodies passed through `transform_response`.

---

## 14. Dashboard architecture

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

## 17. AWS architecture (enhancement layer)

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

## 18. Repository structure and ownership

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

## 20. Demo architecture

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

## 21. Demo reset / recovery

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

## 22. 30-hour timeline

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

**ATK-01 · ExampleCorp origin site · P0**
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

## 27. Definition of Done

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
