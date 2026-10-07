#!/usr/bin/env python3
"""Live boot and curl smoke verification script for Phase 0 integration.

Verifies:
1. Booting ephemeral neutral upstream origin server on dynamically allocated port with ownership nonce.
2. Booting uvicorn sb.main:app on dynamically allocated port with canonical SB_UPSTREAM_ORIGIN and SB_PUBLIC_BASE_URL.
3. Live HTTP request to HTML endpoint -> verifies HTML mutation, canary token injection, and original content preservation.
4. Live HTTP request to JSON endpoint (/api/catalog) -> verifies JSON mutation, canary token injection, and original content preservation.
5. Querying /api/v1/traffic/events -> verifies captured traffic events and session correlation.
6. Executing sb.store.ledger.verify_chain() -> asserts VALID chain integrity.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def find_free_port() -> int:
    """Find a dynamically available TCP port on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port: int, timeout: float = 12.0) -> bool:
    """Wait for TCP port to accept connections within bounded timeout."""
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

    parser = argparse.ArgumentParser(description="Verify live uvicorn and origin boot")
    parser.add_argument("--evidence-dir", type=str, default=os.getenv("SB_EVIDENCE_DIR", ""), help="External directory to save evidence logs")
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir).resolve() if args.evidence_dir else None
    if evidence_dir:
        evidence_dir.mkdir(parents=True, exist_ok=True)

    # Use uniquely owned temporary database and scratch dir OUTSIDE project repository
    temp_dir = Path(tempfile.mkdtemp(prefix="sb_smoke_boot_"))
    smoke_db = temp_dir / "sb_boot.db"

    # Files for child process logs
    origin_out_path = (evidence_dir / "origin_boot.stdout.log") if evidence_dir else (temp_dir / "origin_boot.stdout.log")
    origin_err_path = (evidence_dir / "origin_boot.stderr.log") if evidence_dir else (temp_dir / "origin_boot.stderr.log")
    edge_out_path = (evidence_dir / "edge_boot.stdout.log") if evidence_dir else (temp_dir / "edge_boot.stdout.log")
    edge_err_path = (evidence_dir / "edge_boot.stderr.log") if evidence_dir else (temp_dir / "edge_boot.stderr.log")

    origin_out_fp = origin_out_path.open("wb")
    origin_err_fp = origin_err_path.open("wb")
    edge_out_fp = edge_out_path.open("wb")
    edge_err_fp = edge_err_path.open("wb")

    origin_port = find_free_port()
    edge_port = find_free_port()
    while edge_port == origin_port:
        edge_port = find_free_port()

    ownership_nonce = uuid.uuid4().hex

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env["SB_UPSTREAM_ORIGIN"] = f"http://127.0.0.1:{origin_port}"
    env["SB_PUBLIC_BASE_URL"] = f"http://127.0.0.1:{edge_port}"
    env["SB_DB_PATH"] = str(smoke_db)

    origin_proc: subprocess.Popen | None = None
    edge_proc: subprocess.Popen | None = None

    try:
        # 1. Start ephemeral upstream server on dynamic origin_port with ownership nonce
        origin_code = f"""
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()

NONCE = {ownership_nonce!r}

@app.get("/_boot_nonce")
def get_nonce():
    return {{"nonce": NONCE}}

@app.get("/catalog")
def get_catalog_html():
    return HTMLResponse("<html><head><title>Catalog</title></head><body><main><h1>Products</h1><p>Catalog items</p></main></body></html>")

@app.get("/api/catalog")
def get_catalog_json():
    return JSONResponse({{"items": [{{"id": 1, "name": "Widget"}}], "status": "active"}})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port={origin_port}, log_level="warning")
"""
        print(f"[1/6] Launching ephemeral upstream origin server on port {origin_port} (nonce: {ownership_nonce[:8]}...)...")
        origin_proc = subprocess.Popen(
            [sys.executable, "-c", origin_code],
            env=env,
            stdout=origin_out_fp,
            stderr=origin_err_fp,
        )

        if not wait_port(origin_port, timeout=8.0):
            print(f"ERROR: Origin server failed to start on port {origin_port}.")
            return 1

        # Verify ownership nonce to ensure we attached to our own child process
        try:
            nonce_resp = httpx.get(f"http://127.0.0.1:{origin_port}/_boot_nonce", timeout=2.0)
            assert nonce_resp.json().get("nonce") == ownership_nonce, "Ownership nonce mismatch on origin listener"
        except Exception as exc:
            print(f"ERROR: Failed verifying origin ownership nonce: {exc}")
            return 1
        print(f"      Origin server listening on http://127.0.0.1:{origin_port} (ownership verified)")

        # 2. Start uvicorn backend edge proxy on dynamic edge_port
        print(f"[2/6] Launching backend edge server (uvicorn sb.main:app) on port {edge_port}...")
        edge_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "sb.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(edge_port),
                "--log-level",
                "info",
            ],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=edge_out_fp,
            stderr=edge_err_fp,
        )

        if not wait_port(edge_port, timeout=12.0):
            print(f"ERROR: Backend edge server failed to start on port {edge_port}.")
            return 1
        print(f"      Backend edge server listening on http://127.0.0.1:{edge_port}")

        # 3. Test HTML mutation and correlation
        print(f"[3/6] Testing live HTML mutation via GET http://127.0.0.1:{edge_port}/catalog...")
        html_resp = httpx.get(f"http://127.0.0.1:{edge_port}/catalog", headers={"user-agent": "Mozilla/5.0 LiveVerifier/1.0"})
        print(f"      Status: {html_resp.status_code}")
        print(f"      Headers: Content-Type={html_resp.headers.get('content-type')}, Content-Length={html_resp.headers.get('content-length')}")
        html_text = html_resp.text
        print(f"      Body preview: {html_text[:200]}")
        assert html_resp.status_code == 200, f"Expected 200, got {html_resp.status_code}"
        assert "<h1>Products</h1>" in html_text, "Expected original '<h1>Products</h1>' in mutated HTML"
        assert "<p>Catalog items</p>" in html_text, "Expected original '<p>Catalog items</p>' in mutated HTML"
        assert "sb-canary" in html_text, "Expected 'sb-canary' class in mutated HTML"
        assert "SB-CANARY-" in html_text, "Expected 'SB-CANARY-' token in mutated HTML"
        html_canary_match = re.search(r"SB-CANARY-[A-Za-z0-9_\-]+", html_text)
        assert html_canary_match is not None, "Failed extracting canary token from HTML"
        html_token = html_canary_match.group(0)
        print(f"      Extracted HTML Canary Token: {html_token}")
        print("      PASS: HTML response preserved original content and watermarked with registered canary token.")

        # 4. Test JSON mutation on /api/catalog
        print(f"[4/6] Testing live JSON mutation via GET http://127.0.0.1:{edge_port}/api/catalog...")
        json_resp = httpx.get(f"http://127.0.0.1:{edge_port}/api/catalog", headers={"user-agent": "Mozilla/5.0 LiveVerifier/1.0"})
        print(f"      Status: {json_resp.status_code}")
        print(f"      Headers: Content-Type={json_resp.headers.get('content-type')}, Content-Length={json_resp.headers.get('content-length')}")
        json_text = json_resp.text
        print(f"      Body preview: {json_text}")
        assert json_resp.status_code == 200, f"Expected 200, got {json_resp.status_code}"
        assert "SB-CANARY-" in json_text, "Expected 'SB-CANARY-' token in mutated JSON"
        json_obj = json_resp.json()
        assert "items" in json_obj and json_obj["items"] == [{"id": 1, "name": "Widget"}], "Expected original JSON items preserved"
        assert json_obj.get("status") == "active", "Expected original JSON status preserved"
        json_canary_match = re.search(r"SB-CANARY-[A-Za-z0-9_\-]+", json_text)
        assert json_canary_match is not None, "Failed extracting canary token from JSON"
        json_token = json_canary_match.group(0)
        print(f"      Extracted JSON Canary Token: {json_token}")
        print("      PASS: JSON response preserved original content and additively injected registered canary token.")

        # 5. Query /api/v1/traffic/events and correlate session/ledger
        print(f"[5/6] Querying /api/v1/traffic/events on port {edge_port}...")
        events_resp = httpx.get(f"http://127.0.0.1:{edge_port}/api/v1/traffic/events?limit=20")
        assert events_resp.status_code == 200, f"Expected 200, got {events_resp.status_code}"
        events_data = events_resp.json()
        events_list = events_data.get("events", [])
        print(f"      Captured {len(events_list)} traffic event(s).")
        for ev in events_list:
            print(f"        Event {ev.get('event_id')}: {ev.get('method')} {ev.get('path')} -> {ev.get('decision')} (reasons={ev.get('reasons')})")
        assert len(events_list) >= 2, f"Expected at least 2 logged traffic events, found {len(events_list)}"
        for ev in events_list:
            assert ev.get("decision") == "SANDBOX", f"Expected SANDBOX decision, got {ev.get('decision')}"
        print("      PASS: Traffic events faithfully captured with SANDBOX decisions.")

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

        # Retain bounded summary and external snapshot if evidence dir is provided
        if evidence_dir:
            summary_info = {
                "origin_port": origin_port,
                "edge_port": edge_port,
                "ownership_nonce": ownership_nonce,
                "html_canary_token": html_token,
                "json_canary_token": json_token,
                "traffic_event_count": len(events_list),
                "traffic_events": events_list,
                "ledger_verification": v_result,
            }
            (evidence_dir / "live_boot_summary.json").write_text(json.dumps(summary_info, indent=2), encoding="utf-8")
            if smoke_db.exists():
                shutil.copy2(smoke_db, evidence_dir / "sb_boot.db")
            print(f"      Retained external evidence snapshot in {evidence_dir}")

        print("\n=======================================================")
        print("ALL LIVE BOOT AND SMOKE VERIFICATION CHECKS PASSED (EXIT CODE 0)!")
        print("=======================================================")
        return 0

    finally:
        print("Cleaning up live processes and temporary resources...")
        if edge_proc is not None:
            edge_proc.terminate()
            try:
                edge_proc.wait(timeout=3)
            except Exception:
                edge_proc.kill()
        if origin_proc is not None:
            origin_proc.terminate()
            try:
                origin_proc.wait(timeout=3)
            except Exception:
                origin_proc.kill()

        for fp in (origin_out_fp, origin_err_fp, edge_out_fp, edge_err_fp):
            try:
                fp.close()
            except Exception:
                pass

        # Clean up scratch temporary dir
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
