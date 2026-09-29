"""E2E harness (ATK-05): real processes, real Playwright.

* Target site: the CampusCart profile in ``attacks/sites.py`` (plan §I.A C1), reached
  only through the local edge. ``SB_E2E_SITE=examplecorp`` selects the LOCAL TEST
  FIXTURE (the v1 ExampleCorp stand-in, started on :8001 if it is not already up).
* ``stack`` (session): read-only upstream self-check (plan §I.F), starts the backend
  (:8000, ``UPSTREAM_ORIGIN`` = the profile's origin) only if it is not already
  healthy, waits for ``/api/v1/health`` (<= 20 s) and tears down only what it
  started. An already-running edge must have been started with that upstream.
* ``reset`` (function): ``POST /api/v1/demo/reset`` (the ``make reset`` equivalent).
* ``wait_for(predicate, timeout)``: polls every 0.5 s, never fixed sleeps.
* ``@pytest.mark.requires(module, ...)``: missing cross-owner modules turn the test into
  ``xfail(strict=True)`` naming the dependency, so it flips to a hard failure once the
  dependency lands and the test would pass unmarked.
* ``@pytest.mark.headed``: skipped with an explicit reason when no display is available.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
ATTACKS = REPO / "attacks"
if str(ATTACKS) not in sys.path:
    sys.path.insert(0, str(ATTACKS))

from sites import ANCHORS, SITES  # noqa: E402  (stdlib-only profile module)

EDGE = os.environ.get("SB_EDGE_URL", "http://127.0.0.1:8000")
SITE_NAME = os.environ.get("SB_E2E_SITE", "campuscart")
SITE = SITES[SITE_NAME]
LOCAL_FIXTURE_SITE = "examplecorp"  # v1 ExampleCorp stand-in (demo_site/, :8001): local tests only
# Not UPSTREAM_ORIGIN: backend/tests/conftest.py pins that to :8001 for the unit suites.
ORIGIN = os.environ.get("SB_E2E_ORIGIN", SITE.origin)
STARTUP_TIMEOUT_S = 20
POLL_S = 0.5
HEALTH = "/api/v1/health"  # INT-05 Control API (the plan's bare /health is proxied to the origin)

# Cross-owner modules the scenarios depend on (§18 ownership, §22.3 task cards).
OWNERS = {
    "sb.main": "INT-04 Anirudh: app factory",
    "sb.main:demo_router": "INT-04 Anirudh: mount sb.api.demo.router in sb.main before the catch-all route",
    "sb.store.db": "INT-03 Anirudh: store/reset_db",
    "sb.hooks": "INT-04 Anirudh: trap_hooks + register_reset_hook registry",
    "sb.edge.pipeline": "INT-04 Anirudh: edge pipeline",
    "sb.edge.layer1": "INT-06 Anirudh: Layer 1",
    "sb.edge.layer2": "INT-07 Anirudh: Layer 2",
    "sb.edge.intel": "INT-08 Anirudh: classification",
    "sb.trap.layer3": "TRP-01 Hardik: honeypots/decoys",
    "sb.trap.injector": "TRP-02 Hardik: canary injection/exposures",
    "sb.canary.seed": "CAN-01 Hardik: seed_canaries",
    "sb.provenance.dataset": "PRV-01/PRV-06 Hardik: ingest",
    "sb.provenance.doberman": "PRV-03 Hardik: probes",
    "sb.provenance.correlate": "PRV-04 Hardik: correlation",
    "sb.provenance.evidence": "PRV-05 Hardik: evidence + verify",
}

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


DEMO_ROUTER = "sb.main:demo_router"


def demo_router_mounted() -> bool:
    """``sb.main.app`` includes ``sb.api.demo.router`` (listed in its OpenAPI paths).

    Mounting it behind the proxy catch-all is not detected here; the scenarios then fail
    loudly on ``POST /api/v1/demo/reset``, which is the intended signal.
    """
    try:
        app = importlib.import_module("sb.main").app
        return "/api/v1/demo/reset" in app.openapi().get("paths", {})
    except (ImportError, AttributeError):
        return False


def missing_modules(*modules: str) -> list[str]:
    out = []
    for mod in modules:
        if mod == DEMO_ROUTER:
            found = demo_router_mounted()
        else:
            try:
                found = importlib.util.find_spec(mod) is not None
            except (ImportError, ValueError):
                found = False
        if not found:
            out.append(f"{mod} ({OWNERS.get(mod, 'unknown owner')})")
    return out


def display_available() -> tuple[bool, str]:
    if os.environ.get("SB_NO_DISPLAY"):
        return False, "SB_NO_DISPLAY is set"
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False, "no DISPLAY/WAYLAND_DISPLAY"
    return True, ""


def playwright_available() -> tuple[bool, str]:
    if importlib.util.find_spec("playwright") is None:
        return False, "playwright not installed (pip install playwright && playwright install chromium)"
    return True, ""


def pytest_configure(config):
    config.addinivalue_line("markers", "headed: needs a display for a headed Chromium")
    config.addinivalue_line("markers", "browser: drives Playwright Chromium")
    config.addinivalue_line("markers", "requires(*modules): xfail(strict) while a cross-owner module is missing")


def pytest_collection_modifyitems(config, items):
    has_display, why_display = display_available()
    has_pw, why_pw = playwright_available()
    for item in items:
        if item.get_closest_marker("headed") and not has_display:
            item.add_marker(pytest.mark.skip(reason=f"headed browser test skipped: {why_display}"))
        if (item.get_closest_marker("browser") or item.get_closest_marker("headed")) and not has_pw:
            item.add_marker(pytest.mark.skip(reason=why_pw))
        marker = item.get_closest_marker("requires")
        if marker:
            # every scenario resets through POST /api/v1/demo/reset
            gone = missing_modules(*marker.args, DEMO_ROUTER)
            if gone:
                item.add_marker(pytest.mark.xfail(
                    reason="missing dependency: " + "; ".join(gone), strict=True, run=True,
                ))


# ── helpers ───────────────────────────────────────────────────────────
def wait_for(predicate, timeout: float, interval: float = POLL_S, what: str = "condition"):
    """Poll ``predicate`` until it returns a truthy value; return that value."""
    deadline = time.monotonic() + timeout
    last_exc = None
    while True:
        try:
            result = predicate()
            if result:
                return result
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            last_exc = exc
        if time.monotonic() >= deadline:
            raise AssertionError(f"timed out after {timeout}s waiting for {what}" + (f": {last_exc!r}" if last_exc else ""))
        time.sleep(interval)


def _ok(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def check_upstream() -> None:
    """Plan §I.F self-check, read-only: ``GET ORIGIN/`` is 200 with the profile marker.

    One request to the public upstream; 429/5xx or a missing marker stops the run
    (use the golden run), never retried.
    """
    try:
        resp = httpx.get(ORIGIN + "/", timeout=10)
    except httpx.HTTPError as exc:
        pytest.fail(f"upstream {ORIGIN} unreachable ({exc!r}): use the golden run")
    problems = []
    if resp.status_code != 200:
        problems.append(f"HTTP {resp.status_code}")
    if SITE.marker not in resp.text:
        problems.append(f"missing {SITE.marker!r}")
    found = [a for a in ANCHORS if a.lower() in resp.text.lower()]
    if found:
        problems.append(f"canary anchors present upstream {found}")
    if SITE_NAME == LOCAL_FIXTURE_SITE:
        problems += check_local_fixture()
    assert not problems, f"upstream {ORIGIN} self-check failed (report to site owner): " + "; ".join(problems)


def check_local_fixture() -> list[str]:
    """LOCAL TEST FIXTURE only: the ExampleCorp stand-in's §13 contract."""
    problems = []
    for path in SITE.pages:
        resp = httpx.get(ORIGIN + path, timeout=5)
        body = resp.text
        if resp.status_code != 200:
            problems.append(f"{path}: HTTP {resp.status_code}")
            continue
        if SITE.marker not in body:
            problems.append(f"{path}: missing '{SITE.marker}'")
        if len(re.findall(r'<main id="content"', body)) != 1 or len(re.findall(r"<body\b", body)) != 1:
            problems.append(f"{path}: needs exactly one <main id=\"content\"> and one <body>")
    if httpx.get(ORIGIN + "/static/site.css", timeout=5).status_code != 200:
        problems.append("/static/site.css not served")
    return problems


def run_attacker(script: str, *args: str, timeout: float = 240) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ATTACKS / script), "--base", EDGE, *args],
        cwd=REPO, capture_output=True, text=True, timeout=timeout, check=False,
    )
    assert proc.returncode == 0, f"{script} exit {proc.returncode}\n{proc.stderr[-2000:]}"
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    assert lines, f"{script} printed no JSON result\n{proc.stderr[-2000:]}"
    return json.loads(lines[-1])


def items(payload, key: str) -> list:
    return payload[key] if isinstance(payload, dict) else payload


class Api:
    def __init__(self, base: str = EDGE):
        self.client = httpx.Client(base_url=base, timeout=30)

    def get(self, path: str, **params):
        resp = self.client.get(path, params=params or None)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, body: dict | None = None, timeout: float = 30):
        resp = self.client.post(path, json=body or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def events(self, after: int = 0) -> list[dict]:
        out: list[dict] = []
        while True:
            page = self.get("/api/v1/traffic/events", after=after, limit=200)
            batch = page.get("events", [])
            if not batch:
                return out
            out.extend(batch)
            after = page.get("last_seq") or batch[-1]["seq"]

    def sessions(self) -> list[dict]:
        return items(self.get("/api/v1/sessions"), "sessions")

    def session(self, session_id: str) -> dict:
        return self.get(f"/api/v1/sessions/{session_id}")

    def canaries(self) -> list[dict]:
        return items(self.get("/api/v1/canaries"), "canaries")

    def exposures(self) -> dict[str, list[dict]]:
        return {c["canary_id"]: self.get(f"/api/v1/canaries/{c['canary_id']}").get("exposures") or [] for c in self.canaries()}


# ── fixtures ──────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def stack():
    started: list[subprocess.Popen] = []

    def spawn(args: list[str], cwd: Path) -> None:
        env = {**os.environ, "UPSTREAM_ORIGIN": ORIGIN}
        started.append(subprocess.Popen([sys.executable, "-m", "uvicorn", *args], cwd=cwd, env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    try:
        if SITE_NAME == LOCAL_FIXTURE_SITE and not _ok(ORIGIN + "/"):
            spawn(["demo_site.app:app", "--host", "127.0.0.1", "--port", ORIGIN.rsplit(":", 1)[1]], REPO)
            wait_for(lambda: _ok(ORIGIN + "/"), STARTUP_TIMEOUT_S, what="local fixture origin")
        check_upstream()
        if not _ok(EDGE + HEALTH):
            gone = missing_modules("sb.main")
            if gone:
                pytest.fail(f"backend cannot start, missing dependency: {gone[0]}")
            spawn(["sb.main:app", "--host", "127.0.0.1", "--port", EDGE.rsplit(":", 1)[1]], BACKEND)
            wait_for(lambda: _ok(EDGE + HEALTH), STARTUP_TIMEOUT_S, what="backend " + HEALTH)
        yield Api()
    finally:
        for proc in started:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.fixture(scope="session")
def site() -> str:
    """Site profile name the attackers run against (``--site``)."""
    return SITE_NAME


@pytest.fixture
def api(stack) -> Api:
    return stack


@pytest.fixture
def reset(api) -> dict:
    """Fresh demo state (make reset equivalent) before the test."""
    result = api.post("/api/v1/demo/reset", timeout=60)
    assert result["ok"], f"reset failed: {[c for c in result['checks'] if not c['ok']]}"
    return result


@pytest.fixture(name="wait_for")
def wait_for_fixture():
    """``wait_for(predicate, timeout, what=...)`` — 0.5 s API polling helper."""
    return wait_for


@pytest.fixture
def attack(stack):
    """``attack(script, *args, timeout=240) -> dict`` — run an attacker against the edge."""
    return run_attacker
