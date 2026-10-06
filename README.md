# ScrapeBuster v3 Pure Layer 3 Full Offense

ScrapeBuster v3 is an active defense and offensive instrumentation platform designed to detect, track, and attribute automated web scraping without blocking or rate-limiting traffic.

Rather than presenting interactive challenges or dropping suspect requests, ScrapeBuster transparently proxies traffic to upstream application services while unconditionally injecting subtle, trackable offensive markers (canary seeds, decoy paths, watermarked JSON/HTML payloads).

---

## Architecture & Phase 0 Status

ScrapeBuster development is organized into eight staged phases. **Phase 0 (Planning, Governance & Offense Bootstrap)** establishes core proxying and contract boundaries:

- **Unconditional Offensive Mutation**: Eligible HTML and JSON responses from the configured upstream origin undergo sandboxed payload instrumentation.
- **Dual-Origin Mandate**: Strict separation between the internal target origin (`SB_UPSTREAM_ORIGIN`) and public base URL (`SB_PUBLIC_BASE_URL`).
- **Opaque Session Identity**: Server-side opaque session fingerprints; zero client-side clearance cookies or interactive proof-of-work challenges.
- **Forensic Append-Only Ledger**: Cryptographic single SHA-256 hash chain rooted at genesis for all exposure and audit events.
- **Resilient Fallback**: Upstream connection outages yield unmutated 502/504 pass-through with loud telemetry logging; mutation errors trigger deterministic offensive fallback payloads.

---

## Staged Roadmap

| Phase | Title | Status | Scope |
|---|---|---|---|
| **Phase 0** | **Bootstrap & Contracts** | **In Progress** | Governance, cleanup, pure Layer 3 contracts, append-only ledger, and sandbox mutation |
| Phase 1 | Network & Proxy Layer | Planned | Low-level transport handling, TLS inspection, and proxy streaming |
| Phase 2 | Offense Engine & Classification | Planned | Heuristic traffic analysis and dynamic offensive routing |
| Phase 3 | Canary Infrastructure | Planned | Automated canary rotation and canary seed registries |
| Phase 4 | Provenance Tracking | Planned | Correlation engine and cross-session event matching |
| Phase 5 | Evidence Vault & Cloud Storage | Planned | AWS S3 evidence storage with Object Lock audit compliance |
| Phase 6 | Production Control Plane & Deployment | Planned | Production deployment profiles and system orchestrators |
| Phase 7 | Operator Dashboard & Integration | Planned | Real-time forensic dashboard visualizations and investigative tooling |

---

## Quick Start (Phase 0)

### 1. Prerequisites
- Python 3.11+
- Node.js 20+ (for operator dashboard)

### 2. Setup Environment
```bash
# Copy template configuration
cp .env.example .env

# Configure required origins in .env:
# SB_UPSTREAM_ORIGIN=http://127.0.0.1:8001
# SB_PUBLIC_BASE_URL=http://127.0.0.1:8000

# Install dependencies
make setup
```

### 3. Running Services
```bash
# Start backend edge proxy (:8000)
make backend

# In a separate terminal, start operator dashboard (:5173)
make dashboard
```

### 4. Verification & Validation
```bash
# Execute preflight checks
make preflight

# Execute comprehensive Phase 0 pipeline (lint, contracts, unit, integration)
make check
```
