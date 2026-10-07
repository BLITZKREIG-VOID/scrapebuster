#!/usr/bin/env python3
"""Live boot and curl smoke verification script for Phase 0 integration.

Verifies:
1. Booting ephemeral neutral upstream origin server on port 8001.
2. Booting uvicorn sb.main:app on port 8000 with canonical SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL.
3. Live curl/HTTP request to HTML endpoint -> verifies HTML mutation and sb-canary token injection.
4. Live curl/HTTP request to JSON endpoint (/api/catalog) -> verifies JSON mutation and SB-CANARY- injection.
5. Querying /api/v1/traffic/events -> verifies captured traffic events.
6. Executing sb.store.ledger.verify_chain() -> asserts VALID chain integrity.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def wait_port(port: int, timeout: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main() -> int:
    import httpx

    smoke_db = REPO_ROOT / "sb_smoke.db"
    if smoke_db.exists():
        smoke_db.unlink()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env["SB_UPSTREAM_ORIGIN"] = "http://127.0.0.1:8001"
    env["SB_PUBLIC_BASE_URL"] = "http://127.0.0.1:8000"
    env["SB_DB_PATH"] = str(smoke_db)

    # 1. Start ephemeral upstream server on 8001
    origin_code = """
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()

@app.get("/catalog")
def get_catalog_html():
    return HTMLResponse("<html><head><title>Catalog</title></head><body><main><h1>Products</h1><p>Catalog items</p></main></body></html>")

@app.get("/api/catalog")
def get_catalog_json():
    return JSONResponse({"items": [{"id": 1, "name": "Widget"}], "status": "active"})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
"""
    print("[1/6] Launching ephemeral upstream origin server on port 8001...")
    origin_proc = subprocess.Popen(
        [sys.executable, "-c", origin_code],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not wait_port(8001, timeout=8.0):
        print("ERROR: Origin server failed to start on port 8001.")
        origin_proc.kill()
        return 1
    print("      Origin server listening on http://127.0.0.1:8001")

    # 2. Start uvicorn backend edge proxy on port 8000
    print("[2/6] Launching backend edge server (uvicorn sb.main:app) on port 8000...")
    edge_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sb.main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        if not wait_port(8000, timeout=10.0):
            print("ERROR: Backend edge server failed to start on port 8000.")
            out, err = edge_proc.communicate(timeout=2)
            print("Edge stdout:", out.decode("utf-8", errors="replace"))
            print("Edge stderr:", err.decode("utf-8", errors="replace"))
            return 1
        print("      Backend edge server listening on http://127.0.0.1:8000")

        # 3. Test HTML mutation
        print("[3/6] Testing live HTML mutation via GET http://127.0.0.1:8000/catalog...")
        html_resp = httpx.get("http://127.0.0.1:8000/catalog", headers={"user-agent": "Mozilla/5.0 LiveVerifier/1.0"})
        print(f"      Status: {html_resp.status_code}")
        print(f"      Headers: Content-Type={html_resp.headers.get('content-type')}, Content-Length={html_resp.headers.get('content-length')}")
        html_text = html_resp.text
        print(f"      Body preview: {html_text}")
        assert html_resp.status_code == 200, f"Expected 200, got {html_resp.status_code}"
        assert "sb-canary" in html_text, "Expected 'sb-canary' class in mutated HTML"
        assert "SB-CANARY-" in html_text, "Expected 'SB-CANARY-' token in mutated HTML"
        print("      PASS: HTML response watermarked with session-bound sb-canary token.")

        # 4. Test JSON mutation on /api/catalog
        print("[4/6] Testing live JSON mutation via GET http://127.0.0.1:8000/api/catalog...")
        json_resp = httpx.get("http://127.0.0.1:8000/api/catalog", headers={"user-agent": "Mozilla/5.0 LiveVerifier/1.0"})
        print(f"      Status: {json_resp.status_code}")
        print(f"      Headers: Content-Type={json_resp.headers.get('content-type')}, Content-Length={json_resp.headers.get('content-length')}")
        json_text = json_resp.text
        print(f"      Body preview: {json_text}")
        assert json_resp.status_code == 200, f"Expected 200, got {json_resp.status_code}"
        assert "SB-CANARY-" in json_text, "Expected 'SB-CANARY-' token in mutated JSON"
        json_obj = json_resp.json()
        assert "_canary" in json_obj or any("SB-CANARY-" in str(v) for v in json_obj.values()), "Expected canary injected in JSON"
        print("      PASS: JSON response additively mutated with registered SB-CANARY- token.")

        # 5. Query /api/v1/traffic/events
        print("[5/6] Querying /api/v1/traffic/events...")
        events_resp = httpx.get("http://127.0.0.1:8000/api/v1/traffic/events?limit=10")
        assert events_resp.status_code == 200, f"Expected 200, got {events_resp.status_code}"
        events_data = events_resp.json()
        events_list = events_data.get("events", [])
        print(f"      Captured {len(events_list)} traffic event(s).")
        for ev in events_list:
            print(f"        Event {ev.get('event_id')}: {ev.get('method')} {ev.get('path')} -> {ev.get('decision')} (risk={ev.get('risk_score')})")
        assert len(events_list) >= 2, "Expected at least 2 logged traffic events"
        print("      PASS: Traffic events faithfully persisted and queryable.")

        # 6. Verify ledger chain integrity
        print("[6/6] Verifying forensic ledger chain integrity via sb.store.ledger.verify_chain()...")
        os.environ["SB_DB_PATH"] = str(smoke_db)
        from sb.store import db as smoke_db_mod
        from sb.store import ledger as smoke_ledger_mod
        smoke_db_mod.DB_PATH = str(smoke_db)

        v_result = smoke_ledger_mod.verify_chain()
        print(f"      Ledger verification result: {json.dumps(v_result, indent=2)}")
        assert v_result["result"] == "VALID", f"Expected VALID ledger chain, got {v_result['result']}"
        assert v_result["count"] > 0, "Expected non-zero event count in verified ledger"
        assert len(v_result["errors"]) == 0, f"Expected zero errors, got {v_result['errors']}"
        print(f"      PASS: Ledger chain is cryptographically VALID across {v_result['count']} canonical events.")

        print("\n=======================================================")
        print("ALL LIVE VERIFICATION CHECKS PASSED WITH EXIT CODE 0!")
        print("=======================================================")
        return 0

    finally:
        print("Cleaning up live processes and test database...")
        edge_proc.terminate()
        origin_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except Exception:
            edge_proc.kill()
        try:
            origin_proc.wait(timeout=3)
        except Exception:
            origin_proc.kill()
        if smoke_db.exists():
            smoke_db.unlink()
        wal = smoke_db.with_name("sb_smoke.db-wal")
        shm = smoke_db.with_name("sb_smoke.db-shm")
        if wal.exists():
            wal.unlink()
        if shm.exists():
            shm.unlink()


if __name__ == "__main__":
    sys.exit(main())
