"""T-OB-1 — scraper 1 vs Layer 1 (master plan §4, §19). Owner: Arnav (validation only).

The FastAPI app runs in-process (uvicorn in a thread, :8000) unless a backend is
already healthy there; the existing ExampleCorp origin (:8001) is started as a
subprocess if it is not already up. Scraper 1 runs as a real subprocess.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
EDGE = os.environ.get("SB_EDGE_URL", "http://127.0.0.1:8000")
ORIGIN = os.environ.get("SB_ORIGIN_URL", "http://127.0.0.1:8001")
BLOCK_BEFORE_REQUEST = 60

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DEPS = {
    "sb.main": "INT-04 Anirudh: app factory",
    "sb.store.db": "INT-03 Anirudh: store/reset_db",
    "sb.hooks": "INT-04 Anirudh: trap_hooks + register_reset_hook registry",
    "sb.edge.pipeline": "INT-04 Anirudh: edge pipeline",
    "sb.edge.layer1": "INT-06 Anirudh: Layer 1",
    "sb.edge.intel": "INT-08 Anirudh: classification",
    "sb.canary.seed": "CAN-01 Hardik: seed_canaries",
}
HEALTH = "/api/v1/health"  # INT-05 Control API


def _demo_router_mounted() -> bool:
    """sb.main.app includes sb.api.demo.router (the test resets via POST /api/v1/demo/reset)."""
    try:
        import sb.main
        return "/api/v1/demo/reset" in sb.main.app.openapi().get("paths", {})
    except Exception:
        return False


def _missing() -> list[str]:
    out = []
    for mod, owner in DEPS.items():
        try:
            found = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            out.append(f"{mod} ({owner})")
    if not _demo_router_mounted():
        out.append("sb.main:demo_router (INT-04 Anirudh: mount sb.api.demo.router before the catch-all route)")
    return out


MISSING = _missing()
pytestmark = pytest.mark.xfail(
    bool(MISSING), reason="missing dependency: " + "; ".join(MISSING), strict=True, run=True,
)


def _ok(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def _wait(predicate, timeout: float, what: str):
    deadline = time.monotonic() + timeout
    while not (result := predicate()):
        if time.monotonic() >= deadline:
            raise AssertionError(f"timed out waiting for {what}")
        time.sleep(0.5)
    return result


@pytest.fixture(scope="module")
def edge():
    origin_proc = server = thread = None
    if not _ok(ORIGIN + "/"):
        origin_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "demo_site.app:app", "--host", "127.0.0.1", "--port", ORIGIN.rsplit(":", 1)[1]],
            cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _wait(lambda: _ok(ORIGIN + "/"), 20, "origin :8001")
    try:
        if not _ok(EDGE + HEALTH):
            if MISSING:
                pytest.fail("backend cannot start, missing dependency: " + MISSING[0])
            import uvicorn

            server = uvicorn.Server(uvicorn.Config(
                "sb.main:app", host="127.0.0.1", port=int(EDGE.rsplit(":", 1)[1]), log_level="warning",
            ))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            _wait(lambda: _ok(EDGE + HEALTH), 20, "backend " + HEALTH)
        with httpx.Client(base_url=EDGE, timeout=30) as client:
            yield client
    finally:
        if server is not None:
            server.should_exit = True
            thread.join(timeout=10)
        if origin_proc is not None:
            origin_proc.terminate()
            origin_proc.wait(timeout=10)


def _events(client: httpx.Client) -> list[dict]:
    out, after = [], 0
    while True:
        page = client.get("/api/v1/traffic/events", params={"after": after, "limit": 200}).json()
        batch = page.get("events", [])
        if not batch:
            return out
        out.extend(batch)
        after = page.get("last_seq") or batch[-1]["seq"]


def _sessions(client: httpx.Client) -> list[dict]:
    payload = client.get("/api/v1/sessions").json()
    return payload["sessions"] if isinstance(payload, dict) else payload


def test_ordinary_bot_is_throttled_then_blocked(edge):
    reset = edge.post("/api/v1/demo/reset", timeout=60)
    assert reset.status_code == 200 and reset.json()["ok"], reset.text

    proc = subprocess.run(
        [sys.executable, str(REPO / "attacks" / "ordinary_bot.py"), "--base", EDGE, "--site", "examplecorp",
         "--requests", "100", "--threads", "10"],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    bot = json.loads([line for line in proc.stdout.splitlines() if line.startswith("{")][-1])

    events = sorted(
        (e for e in _events(edge) if (e.get("user_agent") or "").startswith("python-requests")),
        key=lambda e: e["seq"],
    )
    assert events, "no traffic events for the bot"
    rows = [(e["seq"], e["decision"], e["reasons"]) for e in events[:5]]
    assert events[0]["decision"] == "THROTTLE", f"first bot event: {rows}"

    session = _wait(
        lambda: next((s for s in _sessions(edge)
                      if s.get("classification") == "BOT_BASIC" and s.get("state") == "BLOCKED"), None),
        15, "a BOT_BASIC session in state BLOCKED",
    )
    own = [e for e in events if e.get("session_id") == session["session_id"]]
    first_block = next((i for i, e in enumerate(own, start=1) if e["decision"] == "BLOCK"), None)
    assert first_block is not None and first_block < BLOCK_BEFORE_REQUEST, (
        f"first BLOCK at request {first_block} of session {session['session_id']}"
    )

    assert bot["content_bodies"] == 0, bot["status_histogram"]
    assert bot["anchors_found"] == []
    reasons = set().union(*(e["reasons"] for e in events))
    assert "L1_AUTOMATION_UA" in reasons, sorted(reasons)
