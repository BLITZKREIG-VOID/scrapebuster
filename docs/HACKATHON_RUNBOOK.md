# ScrapeBusters Hackathon Operator Runbook

Concise operator runbook for initializing, verifying, executing, and recovering ScapeBusters.

## 1. Environment Configuration
Export absolute paths (subcommands cd to `backend/`) and virtualenv PATH:
```bash
export SB_RUNTIME_DIR="$PWD/data/runtime"
export SB_DB_PATH="$SB_RUNTIME_DIR/sb.db"
export SB_LLM_MODEL="qwen2.5:3b"
export PATH="/tmp/sb-venv/bin:$PWD/.venv/bin:$PATH"
mkdir -p "$SB_RUNTIME_DIR"
```

## 2. Service Startup
Start in separate terminals:
1. **Ollama LLM**: `ollama serve`; `qwen2.5:3b` must already be installed. Do not repull/change the model during the presentation.
2. **Backend Edge Proxy**: `make backend` (port 8000; ensure runtime dir exists first)
3. **Judge Dashboard (Required)**: `make dashboard` (port 5173; primary judge evaluation surface)

From the repository root, with services healthy: `make preflight && make reset`.
Stop on a preflight failure or failed reset check; do not launch attacks.

## 3. Human & Baseline Verification
- **Playwright Human Simulation (CLI)**: `python attacks/human_control.py --base http://127.0.0.1:8000 --pages 5`
- **Manual Human Verification**: Open `http://127.0.0.1:8000/`, then visible login/category/events links to verify clean passthrough (`curl -I` is NOT human verification).

## 4. Pipeline Execution (`make demo-step` or `make demo`)
1. **`ordinary_bot`**: Volumetric burst -> Layer 1 wire block (`BOT_BASIC` / `BLOCKED`).
2. **`advanced_scraper`**: Headless browser -> Layer 2 detects webdriver/fingerprint anomaly -> `AUTOMATION` / `RESTRICTED`.
3. **`sophisticated_scraper`**: Stealth solver -> navigates Layer 3 traps, harvests canary tokens.
4. **`ingest_datasets`**: Ingests scraped target dataset and clean control dataset.
5. **`probe`**: Doberman canary extraction probes on target & control models (`qwen2.5:3b`).
6. **`case_check`**: Correlation engine detects provenance (`PROVENANCE_SIGNAL_DETECTED`).
7. **`verify_evidence`**: Validates SHA-256 hash chain and bundle manifest integrity (`VALID`).

## 5. Golden Run & Local/Cloud Storage
- **Capture Golden**: `make capture-golden` only after all seven LIVE steps PASS. Saves the DB, target, both ingested datasets, sealed evidence and chain. Keep this directory intact.
- **Restore Golden**: `make restore-golden` (restores state; dashboard displays `RECORDED RUN`).
- **Truthful Storage**: Defaults to local sealed evidence (`$SB_RUNTIME_DIR/evidence/`). Unset S3 variables truthfully report disabled/local with zero fabricated cloud status.

## 6. Data Preservation & Safe Recovery
- **Canonical Protected Assets**: `data/baseline/`, `data/control/`, `data/datasets/`, `data/evidence/`, `evidence/`, Phase 10/11 manifests and `data/canary_manifest.json` are frozen. Reset deletes only transient datasets in `$SB_RUNTIME_DIR`.
- **Safe Recovery**: Do NOT use `rm -rf` (destroys golden backups). Use `make restore-golden` or `make reset` for runtime reset with canonical data preservation.
