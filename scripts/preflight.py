"""ScapeBusters preflight (ATK-09) — first command of every rehearsal (``make preflight``).

Prints a PASS/WARN/FAIL table and exits 1 on any FAIL. Stdlib only, so it runs
before dependencies are installed.

    python scripts/preflight.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]
MIN_PY = (3, 11)
MIN_NODE = 20
MIN_DISK_GB = 2.0
WARMUP_LIMIT_S = 25.0


def load_env() -> dict[str, str]:
    """``.env`` values overridden by the process environment."""
    env: dict[str, str] = {}
    path = REPO / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("SB_", "AWS_")) or k == "UPSTREAM_ORIGIN"})
    return env


ENV = load_env()
EDGE = ENV.get("SB_EDGE_URL", "http://127.0.0.1:8000")
HEALTH = "/api/v1/health"  # INT-05 Control API
ORIGIN = ENV.get("UPSTREAM_ORIGIN") or ENV.get("SB_ORIGIN_URL") or "https://campuscart-c73de.web.app"
OLLAMA = ENV.get("SB_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = ENV.get("SB_LLM_MODEL", "qwen2.5:3b")
DASHBOARD = "http://127.0.0.1:5173"

rows: list[tuple[str, str, str]] = []


def add(status: str, name: str, detail: str) -> None:
    rows.append((status, name, detail))


def http(method: str, url: str, body: dict | None = None, timeout: float = 5) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def port_open(url: str) -> bool:
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex((parts.hostname, port)) == 0


def check_python() -> None:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PY
    add("PASS" if ok else "FAIL", "python", f"{v.major}.{v.minor}.{v.micro} (need >= {MIN_PY[0]}.{MIN_PY[1]})")


def check_node() -> None:
    node = shutil.which("node")
    if not node:
        add("FAIL", "node", "node not on PATH")
        return
    out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    major = int(re.match(r"v?(\d+)", out).group(1)) if re.match(r"v?(\d+)", out) else 0
    add("PASS" if major >= MIN_NODE else "FAIL", "node", f"{out} (need >= {MIN_NODE})")


def check_ports() -> None:
    for name, url, required in (("backend", EDGE, True), ("origin", ORIGIN, True),
                                ("dashboard", DASHBOARD, False), ("ollama", OLLAMA, True)):
        if port_open(url):
            add("PASS", f"port {name}", f"{url} listening")
        else:
            add("FAIL" if required else "WARN", f"port {name}", f"{url} not listening")


def check_backend_health() -> None:
    url = EDGE + HEALTH
    try:
        code, body = http("GET", url)
    except OSError as exc:
        add("FAIL", "backend health", f"{url} unreachable: {exc}")
        return
    if code != 200:
        add("FAIL", "backend health", f"{url} HTTP {code}")
        return
    health = json.loads(body)
    add("PASS" if health.get("status") == "ok" else "WARN", "backend health",
        f"{url} status={health.get('status')}")
    comps = health.get("components")
    if not isinstance(comps, dict):
        # INT-05 Health is {status} only; origin/db/ollama are checked directly below.
        add("WARN", "health components", "not reported by backend (plan §16 db/origin/llm/s3)")
        return
    for comp, good, warn in (("db", {"ok"}, set()), ("origin", {"ok"}, set()),
                             ("llm", {"ok"}, {"fallback"}), ("s3", {"ok"}, {"disabled"})):
        value = comps.get(comp)
        status = "PASS" if value in good else "WARN" if value in warn else "FAIL"
        add(status, f"health.{comp}", str(value))


def check_origin() -> None:
    try:
        code, body = http("GET", ORIGIN + "/")
    except OSError as exc:
        add("FAIL", "origin", f"{ORIGIN}/ unreachable: {exc}")
        return
    marker = b"<title>campuscart</title>" if "campuscart" in ORIGIN else b"ExampleCorp Nimbus Platform"
    ok = code == 200 and marker in body
    add("PASS" if ok else "FAIL", "origin", f"{ORIGIN}/ HTTP {code}")


def check_ollama() -> None:
    try:
        code, body = http("GET", OLLAMA + "/api/tags")
    except OSError as exc:
        add("FAIL", "ollama reachable", f"{OLLAMA} unreachable: {exc}")
        add("FAIL", "ollama model", f"{MODEL}: not checked")
        add("FAIL", "ollama warm-up", "not run")
        return
    if code != 200:
        add("FAIL", "ollama reachable", f"HTTP {code}")
        return
    add("PASS", "ollama reachable", OLLAMA)
    names = {m.get("name") for m in json.loads(body).get("models", [])}
    if MODEL not in names and f"{MODEL}:latest" not in names:
        add("FAIL", "ollama model", f"{MODEL} not in /api/tags ({sorted(names)}) — ollama pull {MODEL}")
        add("FAIL", "ollama warm-up", "skipped: model missing")
        return
    add("PASS", "ollama model", MODEL)
    started = time.monotonic()
    try:
        code, _ = http("POST", OLLAMA + "/api/generate", {
            "model": MODEL, "prompt": "Reply with OK.", "stream": False,
            "options": {"temperature": 0, "seed": 42, "num_predict": 8},
        }, timeout=WARMUP_LIMIT_S + 5)
    except OSError as exc:
        add("FAIL", "ollama warm-up", f"{exc}")
        return
    elapsed = time.monotonic() - started
    ok = code == 200 and elapsed < WARMUP_LIMIT_S
    add("PASS" if ok else "FAIL", "ollama warm-up", f"HTTP {code} in {elapsed:.1f}s (limit {WARMUP_LIMIT_S:.0f}s)")


def check_playwright() -> None:
    probe = (
        "from playwright.sync_api import sync_playwright\n"
        "import os\n"
        "with sync_playwright() as p:\n"
        "    path = p.chromium.executable_path\n"
        "    print(path if os.path.exists(path) else '')\n"
    )
    proc = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60)
    path = proc.stdout.strip()
    if proc.returncode != 0:
        add("FAIL", "playwright chromium", (proc.stderr.strip().splitlines() or ["import failed"])[-1])
    elif not path:
        add("FAIL", "playwright chromium", "not installed: python -m playwright install chromium")
    else:
        add("PASS", "playwright chromium", path)


def check_db() -> None:
    raw = Path(ENV.get("SB_DB_PATH", "backend/sb.db"))
    path = raw if raw.is_absolute() else REPO / raw
    if not path.parent.is_dir():
        add("FAIL", "db writable", f"directory missing: {path.parent}")
        return
    try:
        if not path.exists():
            # Probe the directory without leaving an empty DB behind for the backend.
            probe = path.parent / ".preflight_probe"
            probe.write_bytes(b"")
            probe.unlink()
            add("PASS", "db writable", f"{path} (not created yet; directory writable)")
            return
        conn = sqlite3.connect(path, timeout=5)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("ROLLBACK")
        finally:
            conn.close()
        add("PASS", "db writable", str(path))
    except (sqlite3.Error, OSError) as exc:
        add("FAIL", "db writable", f"{path}: {exc}")


def check_disk() -> None:
    free_gb = shutil.disk_usage(REPO).free / 1e9
    add("PASS" if free_gb >= MIN_DISK_GB else "FAIL", "disk free", f"{free_gb:.1f} GB (need >= {MIN_DISK_GB:.0f} GB)")


def check_aws() -> None:
    bucket = ENV.get("SB_S3_BUCKET")
    region = ENV.get("AWS_REGION")
    if not bucket or not region:
        add("WARN", "aws (optional)", "SB_S3_BUCKET/AWS_REGION unset: evidence stays PRESERVED_LOCAL")
    else:
        add("PASS", "aws (optional)", f"bucket {bucket} in {region} configured")


def main() -> int:
    for check in (check_python, check_node, check_ports, check_backend_health, check_origin,
                  check_ollama, check_playwright, check_db, check_disk, check_aws):
        try:
            check()
        except Exception as exc:  # a broken check is a FAIL, never a crash
            add("FAIL", check.__name__.removeprefix("check_"), f"{exc.__class__.__name__}: {exc}")
    width = max(len(name) for _, name, _ in rows)
    print(f"{'STATUS':<6}  {'CHECK':<{width}}  DETAIL")
    for status, name, detail in rows:
        print(f"{status:<6}  {name:<{width}}  {detail}")
    fails = sum(1 for s, _, _ in rows if s == "FAIL")
    warns = sum(1 for s, _, _ in rows if s == "WARN")
    print(f"\nPREFLIGHT {'FAIL' if fails else 'PASS'}: {fails} FAIL, {warns} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
